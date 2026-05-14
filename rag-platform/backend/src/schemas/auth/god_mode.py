"""God Mode 相关实体类"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class GodModeEnter(BaseModel):
    """进入 God Mode"""
    tenant_id: str


class GodModeSession(BaseModel):
    """God Mode 会话"""
    access_token: str
    expires_at: datetime
    tenant_id: str
    actor_id: str


class GodModeExtend(BaseModel):
    """延长 God Mode"""
    extend_minutes: int = Field(default=30, ge=1, le=60)


class GodModeAuditLogRead(BaseModel):
    """God Mode 审计日志"""
    id: str
    tenant_id: str
    actor_id: str
    action: str
    target_type: Optional[str] = None
    target_id: Optional[str] = None
    details: Optional[str] = None
    session_started_at: Optional[datetime] = None
    created_at: datetime


class GodModeAuditLogList(BaseModel):
    """God Mode 审计日志列表"""
    items: list[GodModeAuditLogRead]
    total: int
