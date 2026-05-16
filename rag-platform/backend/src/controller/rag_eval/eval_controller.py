"""RAG 评估控制器

路由前缀：/api/v1/rag/eval
包含：测试用例、测试集、草稿、测试运行、报告、调优、快照、趋势
"""
from typing import Any, Optional

from fastapi import APIRouter, Query, Request

from src.schemas.common import APIResponse
from src.schemas.rag_eval.draft import (
    CreateDraftReq,
    GenerateDraftReq,
    ReviewDraftReq,
    UpdateDraftReq,
)
from src.schemas.rag_eval.report import CreateReportReq
from src.schemas.rag_eval.snapshot import CreateSnapshotReq
from src.schemas.rag_eval.test_case import (
    BatchDeleteCasesReq,
    CreateTestCaseReq,
    ImportTestCaseReq,
    UpdateTestCaseReq,
)
from src.schemas.rag_eval.test_run import CompareRunsReq, CreateTestRunReq
from src.schemas.rag_eval.test_set import (
    AddCasesToSetReq,
    CreateTestSetReq,
    RemoveCasesFromSetReq,
    UpdateTestSetReq,
)
from src.schemas.rag_eval.tuning import AdoptSuggestionReq
from src.utils.logger import logger

router = APIRouter(prefix="/api/v1/rag/eval", tags=["RAG评估"])


# ── 测试用例 ──────────────────────────────────────────────


@router.get("/test-cases")
async def list_test_cases(
    request: Request,
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页数量"),
    source: Optional[str] = Query(default=None, description="来源筛选"),
    difficulty: Optional[str] = Query(default=None, description="难度筛选"),
    search: Optional[str] = Query(default=None, description="关键词搜索"),
):
    """列出测试用例"""
    service = request.app.state.case_service
    tenant_id = request.state.tenant_id

    result = await service.list_cases(
        tenant_id=tenant_id,
        page=page,
        page_size=page_size,
        source=source,
        difficulty=difficulty,
        search=search,
    )
    return APIResponse.success(data=result.model_dump())


@router.post("/test-cases")
async def create_test_case(request: Request, data: CreateTestCaseReq):
    """创建测试用例"""
    service = request.app.state.case_service
    tenant_id = request.state.tenant_id

    result = await service.create_case(tenant_id, data)
    return APIResponse.success(data=result.model_dump())


@router.get("/test-cases/{case_id}")
async def get_test_case(request: Request, case_id: str):
    """获取测试用例详情"""
    service = request.app.state.case_service
    tenant_id = request.state.tenant_id

    result = await service.get_case(tenant_id, case_id)
    return APIResponse.success(data=result.model_dump())


@router.put("/test-cases/{case_id}")
async def update_test_case(request: Request, case_id: str, data: UpdateTestCaseReq):
    """更新测试用例"""
    service = request.app.state.case_service
    tenant_id = request.state.tenant_id

    result = await service.update_case(tenant_id, case_id, data)
    return APIResponse.success(data=result.model_dump())


@router.delete("/test-cases/{case_id}")
async def delete_test_case(request: Request, case_id: str):
    """删除测试用例"""
    service = request.app.state.case_service
    tenant_id = request.state.tenant_id

    await service.delete_case(tenant_id, case_id)
    return APIResponse.success(data=None)


@router.post("/test-cases/batch-delete")
async def batch_delete_test_cases(request: Request, data: BatchDeleteCasesReq):
    """批量删除测试用例"""
    service = request.app.state.case_service
    tenant_id = request.state.tenant_id

    await service.batch_delete(tenant_id, data.case_ids)
    return APIResponse.success(data=None)


@router.post("/test-cases/import")
async def import_test_cases(request: Request, data: ImportTestCaseReq):
    """批量导入测试用例"""
    service = request.app.state.case_service
    tenant_id = request.state.tenant_id

    result = await service.import_cases(tenant_id, data.cases)
    return APIResponse.success(data=[r.model_dump() for r in result])


# ── 测试集 ────────────────────────────────────────────────


@router.get("/test-sets")
async def list_test_sets(
    request: Request,
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页数量"),
):
    """列出测试集"""
    service = request.app.state.set_service
    tenant_id = request.state.tenant_id

    result = await service.list_sets(tenant_id, page, page_size)
    return APIResponse.success(data=result.model_dump())


@router.post("/test-sets")
async def create_test_set(request: Request, data: CreateTestSetReq):
    """创建测试集"""
    service = request.app.state.set_service
    tenant_id = request.state.tenant_id
    user_id = request.state.user_id

    result = await service.create_set(tenant_id, user_id, data)
    return APIResponse.success(data=result.model_dump())


@router.get("/test-sets/{set_id}")
async def get_test_set(request: Request, set_id: str):
    """获取测试集详情"""
    service = request.app.state.set_service
    tenant_id = request.state.tenant_id

    result = await service.get_set(tenant_id, set_id)
    return APIResponse.success(data=result.model_dump())


@router.put("/test-sets/{set_id}")
async def update_test_set(request: Request, set_id: str, data: UpdateTestSetReq):
    """更新测试集"""
    service = request.app.state.set_service
    tenant_id = request.state.tenant_id

    result = await service.update_set(tenant_id, set_id, data)
    return APIResponse.success(data=result.model_dump())


@router.delete("/test-sets/{set_id}")
async def delete_test_set(request: Request, set_id: str):
    """删除测试集"""
    service = request.app.state.set_service
    tenant_id = request.state.tenant_id

    await service.delete_set(tenant_id, set_id)
    return APIResponse.success(data=None)


@router.post("/test-sets/{set_id}/cases")
async def add_cases_to_set(request: Request, set_id: str, data: AddCasesToSetReq):
    """向测试集中添加用例"""
    service = request.app.state.set_service
    tenant_id = request.state.tenant_id

    await service.add_cases(tenant_id, set_id, data.case_ids)
    return APIResponse.success(data=None)


@router.delete("/test-sets/{set_id}/cases")
async def remove_cases_from_set(request: Request, set_id: str, data: RemoveCasesFromSetReq):
    """从测试集中移除用例"""
    service = request.app.state.set_service
    tenant_id = request.state.tenant_id

    await service.remove_cases(tenant_id, set_id, data.case_ids)
    return APIResponse.success(data=None)


# ── 草稿 ──────────────────────────────────────────────────


@router.get("/drafts")
async def list_drafts(
    request: Request,
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页数量"),
    status: Optional[str] = Query(default=None, description="状态筛选"),
    search: Optional[str] = Query(default=None, description="关键词搜索"),
):
    """列出草稿"""
    service = request.app.state.draft_service
    tenant_id = request.state.tenant_id

    result = await service.list_drafts(tenant_id, page, page_size, status, search)
    return APIResponse.success(data=result.model_dump())


@router.post("/drafts")
async def create_draft(request: Request, data: CreateDraftReq):
    """创建草稿"""
    service = request.app.state.draft_service
    tenant_id = request.state.tenant_id

    result = await service.create_draft(tenant_id, data)
    return APIResponse.success(data=result.model_dump())


@router.get("/drafts/{draft_id}")
async def get_draft(request: Request, draft_id: str):
    """获取草稿详情"""
    service = request.app.state.draft_service
    tenant_id = request.state.tenant_id

    result = await service.get_draft(tenant_id, draft_id)
    return APIResponse.success(data=result.model_dump())


@router.put("/drafts/{draft_id}")
async def update_draft(request: Request, draft_id: str, data: UpdateDraftReq):
    """更新草稿"""
    service = request.app.state.draft_service
    tenant_id = request.state.tenant_id

    update_data = data.model_dump(exclude_unset=True)
    result = await service.update_draft(tenant_id, draft_id, update_data)
    return APIResponse.success(data=result.model_dump())


@router.delete("/drafts/{draft_id}")
async def delete_draft(request: Request, draft_id: str):
    """删除草稿"""
    service = request.app.state.draft_service
    tenant_id = request.state.tenant_id

    await service.delete_draft(tenant_id, draft_id)
    return APIResponse.success(data=None)


@router.post("/drafts/generate")
async def generate_drafts(request: Request, data: GenerateDraftReq):
    """从文档批量生成草稿"""
    service = request.app.state.draft_service
    tenant_id = request.state.tenant_id

    result = await service.generate_drafts(tenant_id, data)
    return APIResponse.success(data=[r.model_dump() for r in result])


@router.post("/drafts/{draft_id}/review")
async def review_draft(request: Request, draft_id: str, data: ReviewDraftReq):
    """审核草稿（通过/拒绝）"""
    service = request.app.state.draft_service
    tenant_id = request.state.tenant_id

    result = await service.review_draft(tenant_id, draft_id, data.action)
    return APIResponse.success(data=result.model_dump())


@router.post("/drafts/{draft_id}/import")
async def import_draft(request: Request, draft_id: str):
    """将草稿导入为正式测试用例"""
    service = request.app.state.draft_service
    tenant_id = request.state.tenant_id

    result = await service.import_draft(tenant_id, draft_id)
    return APIResponse.success(data=result.model_dump())


# ── 测试运行 ──────────────────────────────────────────────


@router.post("/runs")
async def create_run(request: Request, data: CreateTestRunReq):
    """创建测试运行"""
    # TODO: Phase 7 完整实现
    tenant_id = request.state.tenant_id
    user_id = request.state.user_id

    logger.info(f"创建测试运行请求: tenant={tenant_id}, pipeline={data.pipeline_id}")
    return APIResponse.success(data={"message": "测试运行创建功能待实现"})


@router.get("/runs")
async def list_runs(
    request: Request,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    pipeline_id: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
):
    """列出测试运行"""
    # TODO: Phase 7 完整实现
    return APIResponse.success(data={"items": [], "total": 0})


@router.post("/runs/compare")
async def compare_runs(request: Request, data: CompareRunsReq):
    """对比两次测试运行"""
    # TODO: Phase 7 完整实现
    return APIResponse.success(data={"message": "运行对比功能待实现"})


@router.get("/runs/{run_id}")
async def get_run(request: Request, run_id: str):
    """获取测试运行详情"""
    # TODO: Phase 7 完整实现
    return APIResponse.success(data={"message": "测试运行详情功能待实现"})


@router.delete("/runs/{run_id}")
async def delete_run(request: Request, run_id: str):
    """删除测试运行"""
    # TODO: Phase 7 完整实现
    tenant_id = request.state.tenant_id
    return APIResponse.success(data=None)


@router.post("/runs/batch-delete")
async def batch_delete_runs(request: Request):
    """批量删除测试运行"""
    # TODO: Phase 7 完整实现
    return APIResponse.success(data=None)


@router.post("/runs/{run_id}/execute")
async def execute_run(request: Request, run_id: str):
    """启动测试执行"""
    # TODO: Phase 7 完整实现
    tenant_id = request.state.tenant_id
    logger.info(f"测试运行执行请求: tenant={tenant_id}, run={run_id}")
    return APIResponse.success(data={"message": "测试执行功能待实现"})


@router.post("/runs/{run_id}/cancel")
async def cancel_run(request: Request, run_id: str):
    """取消测试运行"""
    # TODO: Phase 7 完整实现
    return APIResponse.success(data={"message": "取消运行功能待实现"})


@router.get("/runs/{run_id}/metrics")
async def get_run_metrics(request: Request, run_id: str):
    """获取测试运行指标"""
    # TODO: Phase 7 完整实现
    return APIResponse.success(data={"message": "运行指标功能待实现"})


@router.get("/runs/{run_id}/diagnosis")
async def get_run_diagnosis(request: Request, run_id: str):
    """获取测试运行诊断"""
    # TODO: Phase 7 完整实现
    return APIResponse.success(data={"message": "运行诊断功能待实现"})


@router.get("/runs/{run_id}/stream")
async def stream_run_progress(request: Request, run_id: str):
    """SSE 推送运行进度"""
    # TODO: Phase 7 完整实现
    return APIResponse.success(data={"message": "SSE 进度推送功能待实现"})


# ── 报告 ──────────────────────────────────────────────────


@router.get("/reports")
async def list_reports(
    request: Request,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    """列出评估报告"""
    # TODO: Phase 7 完整实现
    return APIResponse.success(data={"items": [], "total": 0})


@router.post("/reports")
async def generate_report(request: Request, data: CreateReportReq):
    """生成评估报告"""
    # TODO: Phase 7 完整实现
    return APIResponse.success(data={"message": "报告生成功能待实现"})


@router.get("/reports/{report_id}")
async def get_report(request: Request, report_id: str):
    """获取评估报告详情"""
    # TODO: Phase 7 完整实现
    return APIResponse.success(data={"message": "报告详情功能待实现"})


@router.delete("/reports/{report_id}")
async def delete_report(request: Request, report_id: str):
    """删除评估报告"""
    # TODO: Phase 7 完整实现
    return APIResponse.success(data=None)


@router.get("/reports/{report_id}/export")
async def export_report(request: Request, report_id: str):
    """导出评估报告"""
    # TODO: Phase 7 完整实现
    return APIResponse.success(data={"message": "报告导出功能待实现"})


# ── 调优 ──────────────────────────────────────────────────


@router.get("/runs/{run_id}/tuning")
async def get_tuning_suggestions(request: Request, run_id: str):
    """获取调优建议"""
    # TODO: Phase 7 完整实现
    return APIResponse.success(data={"items": []})


@router.post("/tuning/{suggestion_id}/adopt")
async def adopt_suggestion(request: Request, suggestion_id: str):
    """采纳调优建议"""
    # TODO: Phase 7 完整实现
    return APIResponse.success(data={"message": "采纳建议功能待实现"})


@router.post("/tuning/{suggestion_id}/reject")
async def reject_suggestion(request: Request, suggestion_id: str):
    """拒绝调优建议"""
    # TODO: Phase 7 完整实现
    return APIResponse.success(data=None)


@router.post("/tuning/{suggestion_id}/ignore")
async def ignore_suggestion(request: Request, suggestion_id: str):
    """忽略调优建议"""
    # TODO: Phase 7 完整实现
    return APIResponse.success(data=None)


@router.get("/config-versions")
async def list_config_versions(request: Request):
    """列出配置版本"""
    # TODO: Phase 7 完整实现
    return APIResponse.success(data={"items": []})


@router.post("/config-versions/{version_id}/rollback")
async def rollback_config_version(request: Request, version_id: str):
    """回滚配置版本"""
    # TODO: Phase 7 完整实现
    return APIResponse.success(data={"message": "配置回滚功能待实现"})


# ── 快照 ──────────────────────────────────────────────────


@router.post("/snapshots")
async def create_snapshot(request: Request, data: CreateSnapshotReq):
    """创建知识库快照"""
    # TODO: Phase 7 完整实现
    tenant_id = request.state.tenant_id
    logger.info(f"快照创建请求: tenant={tenant_id}, kb={data.kb_id}")
    return APIResponse.success(data={"message": "快照创建功能待实现"})


@router.get("/snapshots")
async def list_snapshots(
    request: Request,
    kb_id: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    """列出知识库快照"""
    # TODO: Phase 7 完整实现
    return APIResponse.success(data={"items": [], "total": 0})


@router.get("/snapshots/{snapshot_id}")
async def get_snapshot(request: Request, snapshot_id: str):
    """获取快照详情"""
    # TODO: Phase 7 完整实现
    return APIResponse.success(data={"message": "快照详情功能待实现"})


# ── 趋势 ──────────────────────────────────────────────────


@router.get("/trends")
async def get_trends(
    request: Request,
    pipeline_id: Optional[str] = Query(default=None),
    period: str = Query(default="30d", description="时间范围：7d/30d/90d"),
):
    """获取趋势数据"""
    # TODO: Phase 7 完整实现
    return APIResponse.success(data={"items": []})
