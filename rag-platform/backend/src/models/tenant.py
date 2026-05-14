"""租户数据模型"""
from datetime import datetime

from sqlalchemy import JSON, Column, DateTime, String

from src.models.base import Base


class Tenant(Base):
    """租户表"""
    __tablename__ = "tenants"

    id = Column(String(36), primary_key=True, comment="租户ID (UUID)")
    name = Column(String(255), nullable=False, comment="租户名称")
    slug = Column(String(100), nullable=False, unique=True, comment="租户标识")
    status = Column(String(20), nullable=False, default="active", comment="状态")
    resource_limits = Column(JSON, comment="资源配额")
    deleted_at = Column(DateTime, comment="软删除时间")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
