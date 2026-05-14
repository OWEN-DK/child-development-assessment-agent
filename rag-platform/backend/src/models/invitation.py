"""邀请数据模型"""
from datetime import datetime

from sqlalchemy import JSON, Column, DateTime, String

from src.models.base import Base


class UserInvitation(Base):
    """用户邀请表"""
    __tablename__ = "user_invitations"

    id = Column(String(36), primary_key=True, comment="邀请ID (UUID)")
    tenant_id = Column(String(36), nullable=False, index=True, comment="租户ID")
    email = Column(String(255), nullable=False, comment="被邀请邮箱")
    roles = Column(JSON, nullable=False, comment="角色列表")
    token = Column(String(255), nullable=False, unique=True, comment="邀请令牌")
    expires_at = Column(DateTime, nullable=False, comment="过期时间")
    accepted_at = Column(DateTime, comment="接受时间")
    created_by = Column(String(36), nullable=False, comment="邀请人ID")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
