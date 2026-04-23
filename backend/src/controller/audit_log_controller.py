"""审计日志 API 控制器"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel

from src.core.database import db_session_factory
from src.schemas.common import APIResponse
from src.service.audit_log_service import AuditLogService
from src.utils.serializers import create_serializer, safe_isoformat

router = APIRouter(prefix="/api/v1/rag/test", tags=["RAG Eval Audit Logs"])

audit_log_service = AuditLogService()

serialize_audit_log = create_serializer(
    object,
    {
        "id": None,
        "operator": None,
        "action": None,
        "target_type": None,
        "target_id": None,
        "before_value": None,
        "after_value": None,
        "diff_summary": None,
        "ip_address": None,
        "user_agent": None,
        "created_at": safe_isoformat,
    },
)


class AuditLogQueryParams(BaseModel):
    operator: Optional[str] = None
    action: Optional[str] = None
    target_type: Optional[str] = None
    target_id: Optional[str] = None
    from_date: Optional[datetime] = None
    to_date: Optional[datetime] = None
    page: int = 1
    page_size: int = 20


@router.get("/audit-logs")
async def query_audit_logs(
    operator: Optional[str] = Query(None, description="操作人筛选"),
    action: Optional[str] = Query(None, description="操作类型筛选"),
    target_type: Optional[str] = Query(None, description="目标类型筛选"),
    target_id: Optional[str] = Query(None, description="目标 ID 筛选"),
    from_date: Optional[datetime] = Query(None, description="开始时间"),
    to_date: Optional[datetime] = Query(None, description="结束时间"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """查询审计日志列表"""
    async with db_session_factory() as session:
        logs, total = await audit_log_service.query_logs(
            session=session,
            operator=operator,
            action=action,
            target_type=target_type,
            target_id=target_id,
            from_date=from_date,
            to_date=to_date,
            page=page,
            page_size=page_size,
        )

        return APIResponse.success(data={
            "items": [serialize_audit_log(log) for log in logs],
            "total": total,
            "page": page,
            "page_size": page_size,
        })


@router.get("/audit-logs/{log_id}")
async def get_audit_log(log_id: str):
    """获取审计日志详情"""
    async with db_session_factory() as session:
        log = await audit_log_service.get_log_by_id(session, log_id)

        if not log:
            from src.utils.exceptions import ResourceNotFoundException
            raise ResourceNotFoundException(message=f"审计日志不存在: {log_id}")

        return APIResponse.success(data=serialize_audit_log(log))
