"""管道数据模型"""
from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String, Text

from src.models.base import Base


class Pipeline(Base):
    """管道表"""
    __tablename__ = "pipelines"

    id = Column(String(64), primary_key=True, comment="管道ID (UUID)")
    tenant_id = Column(String(64), nullable=False, index=True, comment="租户ID")
    name = Column(String(255), nullable=False, comment="管道名称")
    description = Column(Text, comment="管道描述")
    type = Column(String(32), nullable=False, default="aggregation", comment="管道类型")
    active_version = Column(Integer, nullable=False, default=1, comment="当前活动版本号")
    status = Column(String(20), nullable=False, default="draft", index=True, comment="状态：draft/active/error")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
