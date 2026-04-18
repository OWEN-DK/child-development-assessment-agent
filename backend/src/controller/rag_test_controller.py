import json
import os
import tempfile
from typing import Dict, List, Optional

from fastapi import (APIRouter, BackgroundTasks, Body, File, Form,
                     Query, UploadFile)
from fastapi.responses import StreamingResponse

from src.api.sse import SSEPublisher, sse_response
from src.schemas import (AddCasesToSetRequest, BatchDeleteRequest,
                         BatchImportRequest, CreateSnapshotRequest,
                         CreateTestCaseRequest, CreateTestSetRequest,
                         GenerateDraftsRequest, ImportDraftsRequest,
                         RunTestsRequest, UpdateDraftRequest,
                         UpdateTestCaseRequest, UpdateTestSetRequest)
from src.schemas.common import APIResponse
from src.schemas.test_case import GenerationParams, TestCase, TestRunStatus
from src.service.rag_test_manager import rag_test_manager
from src.utils.exceptions import (DocumentNotFoundException, DraftNotFoundException,
                                   InvalidParamsException, InternalServerErrorException,
                                   ResourceNotFoundException, TestCaseNotFoundException,
                                   TestRunNotFoundException, TestSetNotFoundException)
from src.utils.logger import logger
from src.utils.serializers import (create_serializer, safe_enum_value,
                                   safe_float, safe_isoformat)

router = APIRouter(prefix="/rag/test", tags=["RAG Test"])

# Phase 2: SSE 工作流
api_router = APIRouter(prefix="/api", tags=["rag-eval-sse"])

serialize_test_case = create_serializer(
    object,
    {
        "id": None,
        "query": None,
        "age": float,
        "domain": safe_enum_value,
        "description": None,
        "expected_knowledge_count": None,
        "answer_points_summary": None,
        "min_age_requirement": safe_float,
        "max_age_requirement": safe_float,
        "difficulty_level": safe_enum_value,
        "expected_knowledge_ids": None,
        "expected_keywords": None,
        "professional_terms": None,
        "source_document_id": None,
        "version": None,
        "created_at": safe_isoformat,
        "updated_at": safe_isoformat,
    }
)

serialize_source_document = create_serializer(
    object,
    {
        "id": None,
        "title": None,
        "file_type": None,
        "file_path": None,
        "file_hash": None,
        "content_summary": None,
        "page_count": None,
        "chapter_structure": None,
        "quality_report": None,
        "status": safe_enum_value,
        "created_at": safe_isoformat,
        "updated_at": safe_isoformat,
    }
)

serialize_draft = create_serializer(
    object,
    {
        "id": None,
        "source_document_id": None,
        "query": None,
        "age": float,
        "domain": safe_enum_value,
        "description": None,
        "expected_knowledge_ids": None,
        "expected_keywords": None,
        "answer_points": None,
        "professional_terms": None,
        "age_requirement": None,
        "generation_params": None,
        "status": safe_enum_value,
        "created_at": safe_isoformat,
        "updated_at": safe_isoformat,
    }
)


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
    result = await rag_test_manager.add_test_case(test_case)
    return APIResponse.success(data=result)


@router.get("/cases")
async def list_test_cases():
    """列出所有测试用例"""
    test_cases = await rag_test_manager.list_test_cases()
    result = [serialize_test_case(tc) for tc in test_cases]
    return APIResponse.success(data=result)


@router.get("/cases/{case_id}")
async def get_test_case(case_id: str):
    """获取单个测试用例"""
    test_case = await rag_test_manager.get_test_case(case_id)
    if not test_case:
        raise TestCaseNotFoundException(case_id=case_id)
    return APIResponse.success(data=test_case)


# JSON导入相关接口
@router.post("/cases/import/preview")
async def preview_import_cases(file: UploadFile = File(...)):
    """预览JSON导入的测试用例"""
    try:
        content = await file.read()
        import_data = json.loads(content.decode("utf-8"))
        valid, invalid, duplicates = await rag_test_manager.preview_import_cases(import_data)
        return APIResponse.success(data={
            "valid_cases": valid,
            "invalid_cases": invalid,
            "duplicates": duplicates,
        })
    except json.JSONDecodeError as e:
        raise InvalidParamsException(message=f"JSON格式错误: {str(e)}")
    except Exception as e:
        raise InternalServerErrorException(message=f"解析失败: {str(e)}")


@router.post("/cases/batch")
async def batch_import_cases(request: BatchImportRequest):
    """批量导入测试用例"""
    try:
        result = await rag_test_manager.batch_import_cases(request.cases, request.test_set_id)
        return APIResponse.success(data=result)
    except ValueError as e:
        raise InvalidParamsException(message=str(e))
    except Exception as e:
        raise InternalServerErrorException(message=f"导入失败: {str(e)}")


@router.put("/cases/{case_id}")
async def update_test_case(case_id: str, request: UpdateTestCaseRequest):
    """更新测试用例"""
    existing = await rag_test_manager.get_test_case(case_id)
    if not existing:
        raise TestCaseNotFoundException(case_id=case_id)

    # 更新字段
    update_data = request.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(existing, field, value)

    updated = await rag_test_manager.update_test_case(case_id, existing)
    if not updated:
        raise InternalServerErrorException(message="Failed to update test case")
    return APIResponse.success(data=updated)


@router.delete("/cases/{case_id}")
async def delete_test_case(case_id: str):
    """删除测试用例"""
    success = await rag_test_manager.delete_test_case(case_id)
    if not success:
        raise TestCaseNotFoundException(case_id=case_id)
    return APIResponse.success(message="Test case deleted")


@router.post("/cases/batch/delete")
async def batch_delete_test_cases(request: BatchDeleteRequest):
    """批量删除测试用例"""
    deleted_count = await rag_test_manager.batch_delete_test_cases(request.ids)
    return APIResponse.success(data={"deleted_count": deleted_count}, message=f"成功删除 {deleted_count} 个测试用例")


# 测试执行
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

    return APIResponse.success(data={"run_id": run_id, "status": "started"})





@router.post("/run/{case_id}")
async def run_single_test(case_id: str, limit: int = Query(10, ge=1, le=50)):
    """运行单个测试用例"""
    test_case = rag_test_manager.get_test_case(case_id)
    if not test_case:
        raise TestCaseNotFoundException(case_id=case_id)

    try:
        result = await rag_test_manager.run_test_case(test_case, limit)
        return APIResponse.success(data={"result": result.model_dump()})
    except Exception as e:
        raise InternalServerErrorException(message=f"Failed to run test: {str(e)}")


# 测试运行结果
@router.get("/runs")
async def list_test_runs():
    """列出所有测试运行"""
    result = rag_test_manager.list_test_runs()
    return APIResponse.success(data=result)


@router.get("/runs/{run_id}")
async def get_test_run(run_id: str):
    """获取单个测试运行结果"""
    run = rag_test_manager.get_test_run(run_id)
    if not run:
        raise TestRunNotFoundException(run_id=run_id)
    return APIResponse.success(data=run)


@router.post("/runs/batch/delete")
async def batch_delete_test_runs(request: BatchDeleteRequest):
    """批量删除测试运行（评估报告）"""
    deleted_count = await rag_test_manager.batch_delete_test_runs(request.ids)
    return APIResponse.success(data={"deleted_count": deleted_count}, message=f"成功删除 {deleted_count} 个评估报告")


@router.get("/compare")
async def compare_test_runs(run_id1: str, run_id2: str):
    """比较两个测试运行的结果"""
    try:
        comparison = rag_test_manager.compare_test_runs(run_id1, run_id2)
        return APIResponse.success(data={"comparison": comparison})
    except ValueError as e:
        raise InvalidParamsException(message=str(e))


# 快照管理
@router.post("/snapshots")
async def create_snapshot(request: CreateSnapshotRequest):
    """创建知识库快照"""
    try:
        snapshot = rag_test_manager.create_snapshot(
            name=request.name, description=request.description
        )
        return APIResponse.success(data={"snapshot": snapshot.model_dump()})
    except Exception as e:
        raise InternalServerErrorException(
            message=f"Failed to create snapshot: {str(e)}"
        )


@router.get("/snapshots")
async def list_snapshots():
    """列出所有快照"""
    result = rag_test_manager.list_snapshots()
    return APIResponse.success(data=result)


@router.get("/snapshots/{snapshot_id}")
async def get_snapshot(snapshot_id: str):
    """获取单个快照"""
    snapshot = rag_test_manager.get_snapshot(snapshot_id)
    if not snapshot:
        raise ResourceNotFoundException(message="Snapshot not found")
    return APIResponse.success(data=snapshot)


@router.post("/snapshots/{snapshot_id}/restore")
async def restore_snapshot(snapshot_id: str, background_tasks: BackgroundTasks):
    """恢复到指定快照"""
    try:
        background_tasks.add_task(rag_test_manager.restore_snapshot, snapshot_id)
        return APIResponse.success(message="Snapshot restore started in background")
    except Exception as e:
        raise InternalServerErrorException(
            message=f"Failed to restore snapshot: {str(e)}"
        )


@router.get("/compare-configs/{version_id1}/{version_id2}")
async def compare_config_versions(version_id1: str, version_id2: str):
    """对比两个配置版本的测试结果"""
    try:
        comparison = rag_test_manager.compare_config_versions(version_id1, version_id2)
        return APIResponse.success(data={"comparison": comparison})
    except ValueError as e:
        raise ResourceNotFoundException(message=str(e))


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

        response_data = {
            "document": serialize_source_document(doc),
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

        return APIResponse.success(data=response_data)
    except ValueError as e:
        raise InvalidParamsException(message=str(e))
    except Exception as e:
        raise InternalServerErrorException(message=f"上传失败: {str(e)}")


@router.get("/documents")
async def list_documents():
    """列出所有源文档"""
    result = await rag_test_manager.list_source_documents()
    return APIResponse.success(data=result)


@router.get("/documents/{doc_id}")
async def get_document(doc_id: str):
    """获取单个源文档"""
    doc = await rag_test_manager.get_source_document(doc_id)
    if not doc:
        raise DocumentNotFoundException(document_id=doc_id)
    return APIResponse.success(data=doc)


@router.delete("/documents/{doc_id}")
async def delete_document(doc_id: str):
    """删除源文档"""
    success = await rag_test_manager.delete_source_document(doc_id)
    if not success:
        raise DocumentNotFoundException(document_id=doc_id)
    return APIResponse.success(message="文档已删除")


# Phase 2: 草稿管理
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
        return APIResponse.success(data={"task_id": task_id}, message="已开始生成测试用例草稿，请通过SSE接口监听进度")
    except ValueError as e:
        raise ResourceNotFoundException(message=str(e))
    except Exception as e:
        raise InternalServerErrorException(message=f"启动生成任务失败: {str(e)}")


@router.get("/drafts/generate/{task_id}/stream")
async def draft_generation_stream(task_id: str) -> StreamingResponse:
    """SSE 实时推送草稿生成进度"""
    return sse_response(f"draft_generation:{task_id}")


@router.get("/drafts")
async def list_drafts(source_document_id: Optional[str] = None):
    """列出草稿"""
    result = await rag_test_manager.list_drafts(source_document_id)
    return APIResponse.success(data=result)


@router.get("/drafts/{draft_id}")
async def get_draft(draft_id: str):
    """获取单个草稿"""
    draft = await rag_test_manager.get_draft(draft_id)
    if not draft:
        raise DraftNotFoundException(draft_id=draft_id)
    return APIResponse.success(data=draft)


@router.put("/drafts/{draft_id}")
async def update_draft(draft_id: str, request: UpdateDraftRequest):
    """更新草稿"""
    updates = request.model_dump(exclude_unset=True)
    draft = await rag_test_manager.update_draft(draft_id, updates)
    if not draft:
        raise DraftNotFoundException(draft_id=draft_id)
    return APIResponse.success(data=draft)


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
                raise DraftNotFoundException(draft_id=draft_id)
            return APIResponse.success(message="草稿已删除")
        
        draft = await rag_test_manager.review_draft(draft_id, action)
        if not draft:
            raise DraftNotFoundException(draft_id=draft_id)
        return APIResponse.success(data={"draft": serialize_draft(draft)})
    except ValueError as e:
        raise InvalidParamsException(message=str(e))


@router.post("/drafts/import")
async def import_drafts(request: ImportDraftsRequest):
    """导入已审核草稿"""
    try:
        result = await rag_test_manager.import_reviewed_drafts(request.draft_ids)
        return APIResponse.success(data=result)
    except Exception as e:
        raise InternalServerErrorException(message=f"导入失败: {str(e)}")


@router.post("/drafts/batch/delete")
async def batch_delete_drafts(request: BatchDeleteRequest):
    """批量删除草稿"""
    deleted_count = await rag_test_manager.batch_delete_drafts(request.ids)
    return APIResponse.success(data={"deleted_count": deleted_count}, message=f"成功删除 {deleted_count} 个草稿")


@router.post("/drafts/{draft_id}/delete")
async def delete_draft(draft_id: str):
    """删除草稿（替代原拒绝功能）"""
    success = await rag_test_manager.delete_draft(draft_id)
    if not success:
        raise DraftNotFoundException(draft_id=draft_id)
    return APIResponse.success(message="草稿已删除")


# Phase 3: 测试集管理
@router.post("/sets")
async def create_test_set(request: CreateTestSetRequest):
    """创建测试集"""
    try:
        test_set = await rag_test_manager.create_test_set(
            request.name, request.description, request.source_type
        )
        return APIResponse.success(data={"test_set": test_set.model_dump()})
    except Exception as e:
        raise InternalServerErrorException(message=f"创建失败: {str(e)}")


@router.get("/sets")
async def list_test_sets():
    """列出所有测试集"""
    result = await rag_test_manager.list_test_sets()
    return APIResponse.success(data=[ts.model_dump() for ts in result])


@router.get("/sets/{set_id}")
async def get_test_set(set_id: str):
    """获取单个测试集"""
    test_set = await rag_test_manager.get_test_set(set_id)
    if not test_set:
        raise TestSetNotFoundException(test_set_id=set_id)
    return APIResponse.success(data=test_set)


@router.put("/sets/{set_id}")
async def update_test_set(set_id: str, request: UpdateTestSetRequest):
    """更新测试集"""
    updates = request.model_dump(exclude_unset=True)
    test_set = await rag_test_manager.update_test_set(set_id, updates)
    if not test_set:
        raise TestSetNotFoundException(test_set_id=set_id)
    return APIResponse.success(data=test_set)


@router.delete("/sets/{set_id}")
async def delete_test_set(set_id: str):
    """删除测试集"""
    success = await rag_test_manager.delete_test_set(set_id)
    if not success:
        raise TestSetNotFoundException(test_set_id=set_id)
    return APIResponse.success(message="测试集已删除")


@router.post("/sets/{set_id}/cases")
async def add_cases_to_set(set_id: str, request: AddCasesToSetRequest):
    """添加测试用例到测试集"""
    test_set = await rag_test_manager.add_test_cases_to_set(set_id, request.case_ids)
    if not test_set:
        raise TestSetNotFoundException(test_set_id=set_id)
    return APIResponse.success(data=test_set)


@router.delete("/sets/{set_id}/cases")
async def remove_cases_from_set(set_id: str, case_ids: List[str] = Query(...)):
    """从测试集移除测试用例"""
    test_set = await rag_test_manager.remove_test_cases_from_set(set_id, case_ids)
    if not test_set:
        raise TestSetNotFoundException(test_set_id=set_id)
    return APIResponse.success(data=test_set)


@router.get("/sets/{set_id}/export")
async def export_test_set(set_id: str):
    """导出测试集为JSON"""
    cases = await rag_test_manager.export_test_set(set_id)
    if cases is None:
        raise TestSetNotFoundException(test_set_id=set_id)
    return APIResponse.success(data=cases)
