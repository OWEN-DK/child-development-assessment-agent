"""调优建议 API 控制器

提供调优建议的查询、状态更新、批量操作、统计等接口
"""

from typing import Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel

from src.core.database import db_session_factory
from src.schemas.common import APIResponse
from src.service.tuning_suggestion_service import TuningSuggestionService
from src.utils.exceptions import ResourceNotFoundException
from src.utils.serializers import create_serializer, safe_isoformat

router = APIRouter(prefix="/api/v1/rag/test", tags=["RAG Eval Tuning Suggestions"])

suggestion_service = TuningSuggestionService()

serialize_suggestion = create_serializer(
    object,
    {
        "id": None,
        "report_id": None,
        "param_name": None,
        "current_value": None,
        "suggested_value": None,
        "action": None,
        "reason": None,
        "expected_effect": None,
        "priority": None,
        "source": None,
        "safe_range": None,
        "applied": None,
        "applied_config_version_id": None,
        "created_at": safe_isoformat,
    },
)


class UpdateSuggestionRequest(BaseModel):
    """更新调优建议状态请求"""
    applied: bool
    applied_config_version_id: Optional[str] = None


class BatchUpdateSuggestionRequest(BaseModel):
    """批量更新调优建议状态请求"""
    ids: list[str]
    applied: bool
    applied_config_version_id: Optional[str] = None


@router.get("/reports/{report_id}/suggestions")
async def get_suggestions(
    report_id: str,
    status: Optional[str] = Query(None, description="状态筛选: pending/applied"),
):
    """获取报告的调优建议列表"""
    async with db_session_factory() as session:
        suggestions = await suggestion_service.get_suggestions_by_report(
            report_id=report_id,
            session=session,
            status=status,
        )

        return APIResponse.success(data=[
            serialize_suggestion(s) for s in suggestions
        ])


@router.get("/reports/{report_id}/suggestions/stats")
async def get_suggestion_stats(report_id: str):
    """获取建议统计"""
    async with db_session_factory() as session:
        stats = await suggestion_service.get_suggestion_stats(
            report_id=report_id,
            session=session,
        )

        return APIResponse.success(data=stats)


@router.patch("/suggestions/{suggestion_id}")
async def update_suggestion(suggestion_id: str, request: UpdateSuggestionRequest):
    """更新建议状态（采纳/取消采纳）"""
    async with db_session_factory() as session:
        suggestion = await suggestion_service.get_suggestion_by_id(
            suggestion_id=suggestion_id,
            session=session,
        )

        if not suggestion:
            raise ResourceNotFoundException(message=f"建议不存在: {suggestion_id}")

        updated = await suggestion_service.update_suggestion_status(
            suggestion_id=suggestion_id,
            applied=request.applied,
            session=session,
            applied_config_version_id=request.applied_config_version_id,
        )

        return APIResponse.success(data=serialize_suggestion(updated))


@router.post("/suggestions/batch-update")
async def batch_update_suggestions(request: BatchUpdateSuggestionRequest):
    """批量更新建议状态"""
    async with db_session_factory() as session:
        updated_count = await suggestion_service.batch_update_suggestions(
            suggestion_ids=request.ids,
            applied=request.applied,
            session=session,
            applied_config_version_id=request.applied_config_version_id,
        )

        return APIResponse.success(data={"updated_count": updated_count})
