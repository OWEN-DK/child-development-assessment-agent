import json
import os
import tempfile
from typing import Dict, List, Optional

from fastapi import (APIRouter, BackgroundTasks, Body, File, Form,
                     Query, UploadFile)
from fastapi.responses import StreamingResponse

from src.api.sse import SSEPublisher, sse_response
from src.schemas import (AddCasesToSetRequest, BatchDeleteRequest,
                         BatchImportRequest, CreateDraftRequest, CreateSnapshotRequest,
                         CreateTestCaseRequest, CreateTestSetRequest,
                         GenerateDraftsRequest, ImportDraftsRequest,
                         RunTestsRequest, UpdateDraftRequest,
                         UpdateTestCaseRequest, UpdateTestSetRequest)
from src.schemas.common import APIResponse
from src.schemas.test_case import GenerationParams, TestCase, TestRunStatus
from src.service.rag_test_manager import rag_test_manager
from src.service.rag_test.draft_service import draft_service
from src.service.task_sse_publisher import TaskSsePublisher
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
        "source_document_name": None,
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

serialize_test_run = create_serializer(
    object,
    {
        "id": None,
        "name": None,
        "description": None,
        "overall_precision": safe_float,
        "overall_recall": safe_float,
        "overall_f1": safe_float,
        "overall_mrr": safe_float,
        "overall_ndcg": safe_float,
        "total_test_cases": None,
        "passed_test_cases": None,
        "status": safe_enum_value,
        "created_at": safe_isoformat,
        "completed_at": safe_isoformat,
        "snapshot_id": None,
        "config_version_id": None,
        "previous_config_version_id": None,
        "config_snapshot": None,
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
                # 推送进度（使用统一 SSE 发布器）
                await TaskSsePublisher.publish_progress(
                    task_type="test_run",
                    task_id=run_id,
                    progress=0,
                    message=f"用例 {test_result.test_case_id} 执行完成",
                    metadata={
                        "test_case_id": test_result.test_case_id,
                        "passed": test_result.passed,
                        "execution_time_ms": test_result.execution_time_ms,
                    }
                )

            await rag_test_manager.execute_batch(
                run_id, request.concurrency, progress_callback
            )

            # 推送完成（使用统一 SSE 发布器）
            await TaskSsePublisher.publish_complete(
                task_type="test_run",
                task_id=run_id,
                result={
                    "status": "completed",
                    "total": total,
                    "passed": test_run.passed_test_cases,
                }
            )

        except Exception as e:
            logger.error(f"测试执行失败：{e}")
            # 推送错误（使用统一 SSE 发布器）
            await TaskSsePublisher.publish_error(
                task_type="test_run",
                task_id=run_id,
                error=str(e)
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
    runs = await rag_test_manager.list_test_runs()
    result = [serialize_test_run(run) for run in runs]
    return APIResponse.success(data=result)


@router.get("/runs/{run_id}")
async def get_test_run(run_id: str):
    """获取单个测试运行结果"""
    run = await rag_test_manager.get_test_run(run_id)
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
        comparison = await rag_test_manager.compare_test_runs(run_id1, run_id2)
        return APIResponse.success(data={"comparison": comparison})
    except ValueError as e:
        raise InvalidParamsException(message=str(e))


# ========== 6 层校验引擎 API ==========

from src.core.database import db_session_factory
from src.service.validation_service import get_validation_service
from src.utils.exceptions import InternalServerErrorException


@router.post("/runs/{run_id}/validate")
async def trigger_validation(run_id: str, background_tasks: BackgroundTasks):
    """手动触发完整校验（Layer 1-6）

    默认只执行 Layer 1-5，Layer 6 需额外指定。
    校验在后台异步执行，不阻塞响应。
    """
    try:
        session_factory = db_session_factory
        validation_service = get_validation_service(session_factory)

        # 获取测试运行（优先 RagEvalTestRun，回退到 legacy TestRun）
        test_run = await _get_rag_eval_test_run(run_id, session_factory)
        if not test_run:
            raise ResourceNotFoundException(run_id=run_id)

        async def _execute_validation():
            try:
                await validation_service.execute_layer1_to_5(test_run)
                logger.info(f"校验完成: run_id={run_id}")
            except Exception as e:
                logger.error(f"校验失败: run_id={run_id}, error={e}")

        background_tasks.add_task(_execute_validation)

        return APIResponse.success(
            data={"run_id": run_id, "status": "started"},
            message="校验已启动，Layer 1-5 在后台执行"
        )
    except ResourceNotFoundException:
        raise
    except Exception as e:
        raise InternalServerErrorException(message=f"触发校验失败: {str(e)}")


@router.post("/runs/{run_id}/validate/layer6")
async def trigger_layer6_validation(run_id: str):
    """手动触发 Layer 6 校验（回归检测、交叉验证、成本分析、A/B 测试）

    Layer 6 需要 Layer 1-5 已完成，否则返回警告。
    """
    try:
        session_factory = db_session_factory
        validation_service = get_validation_service(session_factory)

        test_run = await _get_rag_eval_test_run(run_id, session_factory)
        if not test_run:
            raise ResourceNotFoundException(run_id=run_id)

        result = await validation_service.execute_layer6(test_run)

        return APIResponse.success(
            data={"run_id": run_id, "layer6_result": result},
            message="Layer 6 校验完成"
        )
    except ResourceNotFoundException:
        raise
    except Exception as e:
        raise InternalServerErrorException(message=f"Layer 6 校验失败: {str(e)}")


@router.get("/runs/{run_id}/validation")
async def get_validation_results(run_id: str):
    """获取测试运行的校验结果"""
    try:
        session_factory = db_session_factory
        validation_service = get_validation_service(session_factory)

        report = await validation_service.get_validation_results(run_id)

        return APIResponse.success(data={
            "report_id": report.id,
            "run_id": report.run_id,
            "status": report.status.value if hasattr(report.status, 'value') else report.status,
            "overall_score": report.overall_score,
            "validation_results": report.validation_results,
            "tuning_suggestion_summary": report.tuning_suggestion_summary,
            "created_at": report.created_at.isoformat() if report.created_at else None,
        })
    except ResourceNotFoundException:
        raise
    except Exception as e:
        raise InternalServerErrorException(message=f"获取校验结果失败: {str(e)}")


async def _get_rag_eval_test_run(run_id: str, session_factory):
    """获取 RagEvalTestRun 对象（用于校验引擎）"""
    from sqlalchemy import select
    from src.models.rag_eval.test_run import RagEvalTestRun

    async with session_factory() as session:
        stmt = select(RagEvalTestRun).where(RagEvalTestRun.id == run_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()


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
            # Step 1: 提取书籍元数据
            from src.service.rag_test.book_metadata_service import BookMetadataService
            metadata_service = BookMetadataService()
            full_text = ""
            try:
                if os.path.exists(doc.file_path):
                    with open(doc.file_path, "r", encoding="utf-8", errors="ignore") as f:
                        full_text = f.read()[:4000]
            except Exception:
                full_text = doc.content_summary or ""

            metadata = await metadata_service.extract_metadata(full_text)

            # Step 2: 从配置读取默认参数
            from src.config.modules.rag.testing import TestCaseGenerationConfig
            config = TestCaseGenerationConfig()
            default_domains = [metadata.primary_domain] if metadata.primary_domain else config.default_domains
            default_age_stages = metadata.applicable_age_stages if metadata.applicable_age_stages else config.default_age_stages

            # Step 3: 构建默认组合参数
            params = GenerationParams(
                target_domains=default_domains,
                age_stages=default_age_stages,
                drafts_per_combination=3,
                query_types=["事实性查询", "比较性查询", "方案性查询"],
                difficulty_levels=["入门级", "中级", "高级"],
                llm_model="qwen-plus",
                temperature=0.8,
                mode="append",
            )

            # Step 4: 触发异步生成（使用新方法名）
            task_id = await async_task_manager.start_task(
                task_type="draft_generation",
                task_func=draft_service.generate_drafts_matrix,
                source_document_id=doc.id,
                params=params,
            )

            # Step 5: 返回结果
            response_data["auto_generate_started"] = True
            response_data["task_id"] = task_id
            combinations = len(params.target_domains) * len(params.age_stages)
            response_data["message"] = (
                f"文档上传成功，已开始自动生成 {combinations} 个组合的测试用例草稿，"
                f"请通过 SSE 接口监听进度"
            )

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
        # 参数校验
        params = request.params
        if not params.target_domains:
            raise InvalidParamsException(message="请至少选择一个领域")
        if not params.age_stages:
            raise InvalidParamsException(message="请至少选择一个年龄段")
        if params.drafts_per_combination < 1 or params.drafts_per_combination > 10:
            raise InvalidParamsException(message="每个组合草稿数必须在 1-10 之间")

        # 触发异步生成（使用新方法）
        task_id = await async_task_manager.start_task(
            task_type="draft_generation",
            task_func=draft_service.generate_drafts_matrix,
            source_document_id=doc_id,
            params=params,
        )

        # 返回预估信息
        combinations = len(params.target_domains) * len(params.age_stages)
        total_drafts = combinations * params.drafts_per_combination

        return APIResponse.success(data={
            "task_id": task_id,
            "combinations": combinations,
            "estimated_drafts": total_drafts,
        }, message="已开始生成测试用例草稿，请通过 SSE 接口监听进度")

    except ValueError as e:
        raise ResourceNotFoundException(message=str(e))
    except Exception as e:
        raise InternalServerErrorException(message=f"启动生成任务失败: {str(e)}")


@router.post("/documents/{doc_id}/generate-drafts/estimate")
async def estimate_draft_generation(doc_id: str, request: GenerateDraftsRequest):
    """预估草稿生成的草稿数"""
    params = request.params
    combinations = len(params.target_domains) * len(params.age_stages)
    total_drafts = combinations * params.drafts_per_combination

    return APIResponse.success(data={
        "combinations": combinations,
        "total_drafts": total_drafts,
        "domains": params.target_domains,
        "age_stages": params.age_stages,
        "drafts_per_combination": params.drafts_per_combination,
    })


@router.get("/drafts/generate/{task_id}/stream")
async def draft_generation_stream(task_id: str) -> StreamingResponse:
    """SSE 实时推送草稿生成进度（task_id 为纯 UUID）"""
    return sse_response(f"draft_generation:{task_id}")


@router.post("/drafts/generate/{task_id}/cancel")
async def cancel_draft_generation(task_id: str):
    """取消草稿生成任务"""
    from src.core.async_task import async_task_manager
    
    success = await async_task_manager.cancel_task(task_id, "draft_generation")
    
    if success:
        await SSEPublisher.publish(
            f"draft_generation:{task_id}",
            {
                "type": "cancelled",
                "message": "任务已取消",
                "task_id": task_id
            }
        )
        return APIResponse.success(
            data={"task_id": task_id, "status": "cancelled"},
            message="取消请求已发送"
        )
    else:
        raise ResourceNotFoundException(message=f"任务 {task_id} 不存在或已完成")


@router.get("/drafts/generate/tasks")
async def list_draft_generation_tasks():
    """获取草稿生成任务列表"""
    from src.utils.di import get_task_state_service
    
    task_state_service = get_task_state_service()
    states = await task_state_service.list_recent(task_type="draft_generation", limit=20)
    
    tasks = []
    for state in states:
        tasks.append({
            "task_id": state.task_id,
            "status": state.status.value,
            "progress": state.progress,
            "message": state.message or "草稿生成中",
            "created_at": state.created_at,
            "domain": state.metadata.get("domain", "未知领域"),
            "age_stage": state.metadata.get("age_stage", "未知年龄段"),
            "generated": state.metadata.get("generated", 0),
            "deduplicated": state.metadata.get("deduplicated", 0),
            "total_combinations": state.metadata.get("total_combinations", 0),
            "current_combination": state.metadata.get("current_combination", 0),
        })
    
    return APIResponse.success(data={"tasks": tasks})


@router.get("/drafts")
async def list_drafts(source_document_id: Optional[str] = None):
    """列出草稿"""
    from src.models.document import SourceDocument
    from src.core.database import async_session_factory
    from sqlalchemy import select
    
    result = await rag_test_manager.list_drafts(source_document_id)
    
    # 批量获取来源文档名称
    doc_ids = list(set(d.source_document_id for d in result if d.source_document_id))
    doc_names = {}
    if doc_ids:
        async with async_session_factory() as session:
            docs_result = await session.execute(
                select(SourceDocument.id, SourceDocument.title).where(SourceDocument.id.in_(doc_ids))
            )
            doc_names = {str(doc.id): doc.title for doc in docs_result.all()}
    
    # 转换为字典并填充来源文档名称
    draft_dicts = []
    for draft in result:
        draft_dict = serialize_draft(draft)
        draft_dict["source_document_name"] = doc_names.get(draft.source_document_id, "")
        draft_dicts.append(draft_dict)
    
    return APIResponse.success(data=draft_dicts)


@router.post("/drafts")
async def create_draft(request: CreateDraftRequest):
    """手动创建草稿"""
    try:
        draft = await rag_test_manager.create_draft(
            source_document_id=request.source_document_id,
            query=request.query,
            age=request.age,
            domain=request.domain,
            expected_knowledge_ids=request.expected_knowledge_ids,
            expected_keywords=request.expected_keywords,
            description=request.description,
            answer_points=request.answer_points,
            professional_terms=request.professional_terms,
            age_requirement=request.age_requirement,
        )
        return APIResponse.success(data=serialize_draft(draft))
    except ValueError as e:
        raise InvalidParamsException(message=str(e))
    except Exception as e:
        logger.error(f"创建草稿失败: {e}")
        raise InternalServerErrorException(message="创建草稿失败")


@router.get("/drafts/{draft_id}")
async def get_draft(draft_id: str):
    """获取单个草稿"""
    draft = await rag_test_manager.get_draft(draft_id)
    if not draft:
        raise DraftNotFoundException(draft_id=draft_id)
    
    # 填充来源文档名称
    from src.models.document import SourceDocument
    from src.core.database import async_session_factory
    from sqlalchemy import select
    
    draft_dict = serialize_draft(draft)
    
    async with async_session_factory() as session:
        result = await session.execute(
            select(SourceDocument).where(SourceDocument.id == draft.source_document_id)
        )
        doc = result.scalar_one_or_none()
        if doc:
            draft_dict["source_document_name"] = doc.title
    
    return APIResponse.success(data=draft_dict)


@router.put("/drafts/{draft_id}")
async def update_draft(draft_id: str, request: UpdateDraftRequest):
    """更新草稿"""
    updates = request.model_dump(exclude_unset=True)
    draft = await rag_test_manager.update_draft(draft_id, updates)
    if not draft:
        raise DraftNotFoundException(draft_id=draft_id)
    return APIResponse.success(data=serialize_draft(draft))


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
            request.name, request.description
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


@router.post("/sets/batch/delete")
async def batch_delete_test_sets(request: BatchDeleteRequest):
    """批量删除测试集"""
    deleted_count = await rag_test_manager.batch_delete_test_sets(request.ids)
    return APIResponse.success(data={"deleted_count": deleted_count}, message=f"成功删除 {deleted_count} 个测试集")


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
