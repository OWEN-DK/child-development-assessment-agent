from fastapi import (
    APIRouter,
    HTTPException,
    BackgroundTasks,
    Query,
    UploadFile,
    File,
    Body,
    Form,
)
from fastapi.responses import StreamingResponse
from typing import Optional, List, Dict
from pydantic import BaseModel
import json
import os
import tempfile

from src.models.test_case import TestCase, GenerationParams, TestRunStatus
from src.service.rag_test_manager import rag_test_manager
from src.api.sse import sse_response, SSEPublisher
from src.utils.logger import logger

router = APIRouter(prefix="/rag/test", tags=["RAG Test"])


class CreateTestCaseRequest(BaseModel):
    query: str
    age: int
    expected_knowledge_ids: List[str] = []
    expected_keywords: List[str] = []
    description: str = ""


class UpdateTestCaseRequest(BaseModel):
    query: Optional[str] = None
    age: Optional[int] = None
    expected_knowledge_ids: Optional[List[str]] = None
    expected_keywords: Optional[List[str]] = None
    description: Optional[str] = None


class CreateSnapshotRequest(BaseModel):
    name: str = ""
    description: str = ""


# 测试用例管理
@router.post("/cases")
async def create_test_case(request: CreateTestCaseRequest):
    """创建测试用例"""
    test_case = TestCase(
        query=request.query,
        age=request.age,
        expected_knowledge_ids=request.expected_knowledge_ids,
        expected_keywords=request.expected_keywords,
        description=request.description,
    )
    return await rag_test_manager.add_test_case(test_case)


@router.get("/cases")
async def list_test_cases():
    """列出所有测试用例"""
    test_cases = await rag_test_manager.list_test_cases()
    # SQLAlchemy模型转字典
    result = []
    for tc in test_cases:
        tc_dict = {
            "id": tc.id,
            "query": tc.query,
            "age": float(tc.age),
            "domain": tc.domain.value,
            "description": tc.description,
            "expected_knowledge_count": tc.expected_knowledge_count,
            "answer_points_summary": tc.answer_points_summary,
            "min_age_requirement": float(tc.min_age_requirement) if tc.min_age_requirement else None,
            "max_age_requirement": float(tc.max_age_requirement) if tc.max_age_requirement else None,
            "difficulty_level": tc.difficulty_level.value if tc.difficulty_level else None,
            "expected_knowledge_ids": tc.expected_knowledge_ids,
            "expected_keywords": tc.expected_keywords,
            "professional_terms": tc.professional_terms,
            "source_document_id": tc.source_document_id,
            "version": tc.version,
            "created_at": tc.created_at.isoformat() if tc.created_at else None,
            "updated_at": tc.updated_at.isoformat() if tc.updated_at else None
        }
        result.append(tc_dict)
    return result


@router.get("/cases/{case_id}")
async def get_test_case(case_id: str):
    """获取单个测试用例"""
    test_case = await rag_test_manager.get_test_case(case_id)
    if not test_case:
        raise HTTPException(status_code=404, detail="Test case not found")
    return test_case


# JSON导入相关接口
class BatchImportRequest(BaseModel):
    cases: List[dict]
    test_set_id: Optional[str] = None


@router.post("/cases/import/preview")
async def preview_import_cases(file: UploadFile = File(...)):
    """预览JSON导入的测试用例"""
    try:
        content = await file.read()
        import_data = json.loads(content.decode("utf-8"))
        valid, invalid, duplicates = await rag_test_manager.preview_import_cases(import_data)
        return {
            "valid_cases": valid,
            "invalid_cases": invalid,
            "duplicates": duplicates,
        }
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"JSON格式错误: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"解析失败: {str(e)}")


@router.post("/cases/batch")
async def batch_import_cases(request: BatchImportRequest):
    """批量导入测试用例"""
    try:
        result = await rag_test_manager.batch_import_cases(request.cases, request.test_set_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"导入失败: {str(e)}")


@router.put("/cases/{case_id}")
async def update_test_case(case_id: str, request: UpdateTestCaseRequest):
    """更新测试用例"""
    existing = await rag_test_manager.get_test_case(case_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Test case not found")

    # 更新字段
    update_data = request.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(existing, field, value)

    updated = await rag_test_manager.update_test_case(case_id, existing)
    if not updated:
        raise HTTPException(status_code=500, detail="Failed to update test case")
    return updated


@router.delete("/cases/{case_id}")
async def delete_test_case(case_id: str):
    """删除测试用例"""
    success = await rag_test_manager.delete_test_case(case_id)
    if not success:
        raise HTTPException(status_code=404, detail="Test case not found")
    return {"status": "success", "message": "Test case deleted"}


class BatchDeleteRequest(BaseModel):
    ids: List[str]


@router.post("/cases/batch/delete")
async def batch_delete_test_cases(request: BatchDeleteRequest):
    """批量删除测试用例"""
    deleted_count = await rag_test_manager.batch_delete_test_cases(request.ids)
    return {"status": "success", "message": f"成功删除 {deleted_count} 个测试用例", "deleted_count": deleted_count}


# 测试执行
class RunTestsRequest(BaseModel):
    name: str
    description: str = ""
    test_case_ids: List[str] = None
    test_set_id: str = None
    concurrency: int = Query(5, ge=1, le=20)


@router.post("/run")
async def run_tests(request: RunTestsRequest):
    """运行测试用例"""
    # 创建运行
    run_id = await rag_test_manager.create_test_run(
        name=request.name,
        description=request.description,
        test_case_ids=request.test_case_ids,
        test_set_id=request.test_set_id,
    )

    # 后台执行
    async def _execute_with_progress(run_id: str, concurrency: int):
        """带进度推送的执行"""
        try:
            from src.repository import TestRunRepository

            test_run_repo = TestRunRepository(rag_test_manager.db_session_factory)
            test_run = await test_run_repo.get_by_id(run_id)
            if not test_run:
                raise ValueError(f"Test run not found: {run_id}")
            total = test_run.total_test_cases

            # 执行
            async def progress_callback(test_result):
                # 推送进度
                await SSEPublisher.publish_progress(
                    run_id,
                    {
                        "test_case_id": test_result.test_case_id,
                        "passed": test_result.passed,
                        "execution_time_ms": test_result.execution_time_ms,
                    },
                )

            await rag_test_manager.execute_batch(
                run_id, request.concurrency, progress_callback
            )

            # 推送完成
            await SSEPublisher.publish_complete(
                run_id,
                {
                    "status": "completed",
                    "total": total,
                    "passed": test_run.passed_test_cases,
                },
            )

        except Exception as e:
            logger.error(f"测试执行失败：{e}")
            await SSEPublisher.publish(
                f"test_run:{run_id}",
                {
                    "type": "error",
                    "run_id": run_id,
                    "error": str(e),
                },
            )

    import asyncio

    asyncio.create_task(_execute_with_progress(run_id, request.concurrency))

    return {"run_id": run_id, "status": "started"}


@router.get("/run/{run_id}/stream")
async def test_run_stream(run_id: str) -> StreamingResponse:
    """SSE 进度推送"""
    return sse_response(f"test_run:{run_id}")


@router.post("/run/{case_id}")
async def run_single_test(case_id: str, limit: int = Query(10, ge=1, le=50)):
    """运行单个测试用例"""
    test_case = rag_test_manager.get_test_case(case_id)
    if not test_case:
        raise HTTPException(status_code=404, detail="Test case not found")

    try:
        result = await rag_test_manager.run_test_case(test_case, limit)
        return {"status": "success", "result": result.model_dump()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to run test: {str(e)}")


# 测试运行结果
@router.get("/runs")
async def list_test_runs():
    """列出所有测试运行"""
    return rag_test_manager.list_test_runs()


@router.get("/runs/{run_id}")
async def get_test_run(run_id: str):
    """获取单个测试运行结果"""
    run = rag_test_manager.get_test_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Test run not found")
    return run


@router.post("/runs/batch/delete")
async def batch_delete_test_runs(request: BatchDeleteRequest):
    """批量删除测试运行（评估报告）"""
    deleted_count = await rag_test_manager.batch_delete_test_runs(request.ids)
    return {"status": "success", "message": f"成功删除 {deleted_count} 个评估报告", "deleted_count": deleted_count}


@router.get("/compare")
async def compare_test_runs(run_id1: str, run_id2: str):
    """比较两个测试运行的结果"""
    try:
        comparison = rag_test_manager.compare_test_runs(run_id1, run_id2)
        return {"status": "success", "comparison": comparison}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# 快照管理
@router.post("/snapshots")
async def create_snapshot(request: CreateSnapshotRequest):
    """创建知识库快照"""
    try:
        snapshot = rag_test_manager.create_snapshot(
            name=request.name, description=request.description
        )
        return {"status": "success", "snapshot": snapshot.model_dump()}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to create snapshot: {str(e)}"
        )


@router.get("/snapshots")
async def list_snapshots():
    """列出所有快照"""
    return rag_test_manager.list_snapshots()


@router.get("/snapshots/{snapshot_id}")
async def get_snapshot(snapshot_id: str):
    """获取单个快照"""
    snapshot = rag_test_manager.get_snapshot(snapshot_id)
    if not snapshot:
        raise HTTPException(status_code=404, detail="Snapshot not found")
    return snapshot


@router.post("/snapshots/{snapshot_id}/restore")
async def restore_snapshot(snapshot_id: str, background_tasks: BackgroundTasks):
    """恢复到指定快照"""
    try:
        background_tasks.add_task(rag_test_manager.restore_snapshot, snapshot_id)
        return {
            "status": "success",
            "message": "Snapshot restore started in background",
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to restore snapshot: {str(e)}"
        )


@router.get("/compare-configs/{version_id1}/{version_id2}")
async def compare_config_versions(version_id1: str, version_id2: str):
    """对比两个配置版本的测试结果"""
    try:
        comparison = rag_test_manager.compare_config_versions(version_id1, version_id2)
        return {"status": "success", "comparison": comparison}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# Phase 2: 源文档管理
@router.post("/documents/upload")
async def upload_document(
    file: UploadFile = File(...),
    title: str = Form(None),
    auto_generate: str = Form("true"),
):
    """上传源文档"""
    try:
        auto_gen = auto_generate.lower() in ("true", "1", "yes")

        suffix = os.path.splitext(file.filename)[1] if file.filename else ".pdf"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name

        doc_title = title or file.filename or "未命名文档"
        file_type = suffix.lstrip(".").upper()

        doc = await rag_test_manager.upload_source_document(
            tmp_path, doc_title, file_type
        )
        os.unlink(tmp_path)

        # SQLAlchemy模型转字典
        doc_dict = {
            "id": doc.id,
            "title": doc.title,
            "file_type": doc.file_type,
            "file_path": doc.file_path,
            "file_hash": doc.file_hash,
            "content_summary": doc.content_summary,
            "page_count": doc.page_count,
            "chapter_structure": doc.chapter_structure,
            "quality_report": doc.quality_report,
            "status": doc.status.value,
            "created_at": doc.created_at.isoformat() if doc.created_at else None,
            "updated_at": doc.updated_at.isoformat() if doc.updated_at else None
        }
        response_data = {
            "status": "success",
            "document": doc_dict,
            "drafts": [],
            "draft_count": 0,
            "auto_generate_started": False,
            "task_id": None
        }

        if auto_gen:
            params = GenerationParams(
                target_domains=["感觉统合"],
                age_range=(0, 6),
                count=10,
                difficulty="medium",
                llm_model="qwen-turbo",
                temperature=0.7,
            )

            # 一行代码启动异步任务
            task_id = await async_task_manager.start_task(
                task_type="draft_generation",
                task_func=rag_test_manager.generate_test_case_drafts,
                source_document_id=doc.id,
                params=params
            )

            # 更新返回信息
            response_data["auto_generate_started"] = True
            response_data["task_id"] = task_id
            response_data["message"] = "文档上传成功，已开始自动生成测试用例草稿，请通过SSE接口监听进度"

        return response_data
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"上传失败: {str(e)}")


@router.get("/documents")
async def list_documents():
    """列出所有源文档"""
    return await rag_test_manager.list_source_documents()


@router.get("/documents/{doc_id}")
async def get_document(doc_id: str):
    """获取单个源文档"""
    doc = await rag_test_manager.get_source_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")
    return doc


@router.delete("/documents/{doc_id}")
async def delete_document(doc_id: str):
    """删除源文档"""
    success = await rag_test_manager.delete_source_document(doc_id)
    if not success:
        raise HTTPException(status_code=404, detail="文档不存在")
    return {"status": "success", "message": "文档已删除"}


# Phase 2: 草稿管理
class GenerateDraftsRequest(BaseModel):
    params: GenerationParams


from src.core.async_task import async_task_manager

@router.post("/documents/{doc_id}/generate-drafts")
async def generate_drafts(doc_id: str, request: GenerateDraftsRequest):
    """根据源文档生成测试用例草稿（异步后台任务，返回task_id用于SSE监听进度）"""
    try:
        # 一行代码启动异步任务，自动处理SSE进度推送、异常处理、消息通知
        task_id = await async_task_manager.start_task(
            task_type="draft_generation",
            task_func=rag_test_manager.generate_test_case_drafts,
            source_document_id=doc_id,
            params=request.params
        )

        # 立即返回任务ID
        return {"status": "started", "task_id": task_id, "message": "已开始生成测试用例草稿，请通过SSE接口监听进度"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"启动生成任务失败: {str(e)}")


@router.get("/drafts/generate/{task_id}/stream")
async def draft_generation_stream(task_id: str) -> StreamingResponse:
    """SSE 实时推送草稿生成进度"""
    return sse_response(f"draft_generation:{task_id}")


@router.get("/drafts")
async def list_drafts(source_document_id: Optional[str] = None):
    """列出草稿"""
    return await rag_test_manager.list_drafts(source_document_id)


@router.get("/drafts/{draft_id}")
async def get_draft(draft_id: str):
    """获取单个草稿"""
    draft = await rag_test_manager.get_draft(draft_id)
    if not draft:
        raise HTTPException(status_code=404, detail="草稿不存在")
    return draft


class UpdateDraftRequest(BaseModel):
    query: Optional[str] = None
    age: Optional[int] = None
    domain: Optional[str] = None
    expected_knowledge_ids: Optional[List[str]] = None
    expected_keywords: Optional[List[str]] = None
    description: Optional[str] = None
    answer_points: Optional[List[str]] = None
    professional_terms: Optional[List[str]] = None
    age_requirement: Optional[str] = None


@router.put("/drafts/{draft_id}")
async def update_draft(draft_id: str, request: UpdateDraftRequest):
    """更新草稿"""
    updates = request.model_dump(exclude_unset=True)
    draft = await rag_test_manager.update_draft(draft_id, updates)
    if not draft:
        raise HTTPException(status_code=404, detail="草稿不存在")
    return draft


@router.post("/drafts/{draft_id}/review")
async def review_draft(
    draft_id: str, action: str = Query(..., description="reviewed")
):
    """审核草稿
    注意：原reject动作已改为直接删除草稿，请使用DELETE /drafts/{draft_id}接口
    """
    try:
        if action == "rejected":
            # 拒绝改为直接删除
            success = await rag_test_manager.delete_draft(draft_id)
            if not success:
                raise HTTPException(status_code=404, detail="草稿不存在")
            return {"status": "success", "message": "草稿已删除"}
        
        draft = await rag_test_manager.review_draft(draft_id, action)
        if not draft:
            raise HTTPException(status_code=404, detail="草稿不存在")
        # SQLAlchemy模型转字典，处理枚举和日期类型
        draft_dict = {
            "id": draft.id,
            "source_document_id": draft.source_document_id,
            "query": draft.query,
            "age": float(draft.age),
            "domain": draft.domain.value,
            "description": draft.description,
            "expected_knowledge_ids": draft.expected_knowledge_ids,
            "expected_keywords": draft.expected_keywords,
            "answer_points": draft.answer_points,
            "professional_terms": draft.professional_terms,
            "age_requirement": draft.age_requirement,
            "generation_params": draft.generation_params,
            "status": draft.status.value,
            "created_at": draft.created_at.isoformat() if draft.created_at else None,
            "updated_at": draft.updated_at.isoformat() if draft.updated_at else None
        }
        return {"status": "success", "draft": draft_dict}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


class ImportDraftsRequest(BaseModel):
    draft_ids: List[str]


@router.post("/drafts/import")
async def import_drafts(request: ImportDraftsRequest):
    """导入已审核草稿"""
    try:
        result = await rag_test_manager.import_reviewed_drafts(request.draft_ids)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"导入失败: {str(e)}")


@router.post("/drafts/batch/delete")
async def batch_delete_drafts(request: BatchDeleteRequest):
    """批量删除草稿"""
    deleted_count = await rag_test_manager.batch_delete_drafts(request.ids)
    return {"status": "success", "message": f"成功删除 {deleted_count} 个草稿", "deleted_count": deleted_count}


@router.post("/drafts/{draft_id}/delete")
async def delete_draft(draft_id: str):
    """删除草稿（替代原拒绝功能）"""
    success = await rag_test_manager.delete_draft(draft_id)
    if not success:
        raise HTTPException(status_code=404, detail="草稿不存在")
    return {"status": "success", "message": "草稿已删除"}


# Phase 3: 测试集管理
class CreateTestSetRequest(BaseModel):
    name: str
    description: str = ""
    source_type: str = "manual"


@router.post("/sets")
async def create_test_set(request: CreateTestSetRequest):
    """创建测试集"""
    try:
        test_set = rag_test_manager.create_test_set(
            request.name, request.description, request.source_type
        )
        return {"status": "success", "test_set": test_set.model_dump()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"创建失败: {str(e)}")


@router.get("/sets")
async def list_test_sets():
    """列出所有测试集"""
    return rag_test_manager.list_test_sets()


@router.get("/sets/{set_id}")
async def get_test_set(set_id: str):
    """获取单个测试集"""
    test_set = rag_test_manager.get_test_set(set_id)
    if not test_set:
        raise HTTPException(status_code=404, detail="测试集不存在")
    return test_set


class UpdateTestSetRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


@router.put("/sets/{set_id}")
async def update_test_set(set_id: str, request: UpdateTestSetRequest):
    """更新测试集"""
    updates = request.model_dump(exclude_unset=True)
    test_set = rag_test_manager.update_test_set(set_id, updates)
    if not test_set:
        raise HTTPException(status_code=404, detail="测试集不存在")
    return test_set


@router.delete("/sets/{set_id}")
async def delete_test_set(set_id: str):
    """删除测试集"""
    success = rag_test_manager.delete_test_set(set_id)
    if not success:
        raise HTTPException(status_code=404, detail="测试集不存在")
    return {"status": "success", "message": "测试集已删除"}


class AddCasesToSetRequest(BaseModel):
    case_ids: List[str]


@router.post("/sets/{set_id}/cases")
async def add_cases_to_set(set_id: str, request: AddCasesToSetRequest):
    """添加测试用例到测试集"""
    test_set = rag_test_manager.add_test_cases_to_set(set_id, request.case_ids)
    if not test_set:
        raise HTTPException(status_code=404, detail="测试集不存在")
    return test_set


@router.delete("/sets/{set_id}/cases")
async def remove_cases_from_set(set_id: str, case_ids: List[str] = Query(...)):
    """从测试集移除测试用例"""
    test_set = rag_test_manager.remove_test_cases_from_set(set_id, case_ids)
    if not test_set:
        raise HTTPException(status_code=404, detail="测试集不存在")
    return test_set


@router.get("/sets/{set_id}/export")
async def export_test_set(set_id: str):
    """导出测试集为JSON"""
    cases = rag_test_manager.export_test_set(set_id)
    if cases is None:
        raise HTTPException(status_code=404, detail="测试集不存在")
    return cases
