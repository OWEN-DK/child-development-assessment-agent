"""角色数据模型"""
from datetime import datetime

from sqlalchemy import JSON, Boolean, Column, DateTime, String
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class Role(Base):
    """角色表"""
    __tablename__ = "roles"

    id = Column(String(36), primary_key=True, comment="角色ID (UUID)")
    tenant_id = Column(String(36), nullable=False, index=True, comment="租户ID")
    name = Column(String(100), nullable=False, comment="角色名称")
    slug = Column(String(100), nullable=False, comment="角色标识")
    permissions = Column(JSON, nullable=False, comment="权限列表")
    is_builtin = Column(Boolean, nullable=False, default=False, comment="是否内置角色")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
