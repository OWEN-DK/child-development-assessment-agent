"""管道版本数据模型"""
from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String, Text

from src.models.base import Base


class PipelineVersion(Base):
    """管道版本表"""
    __tablename__ = "pipeline_versions"

    id = Column(String(64), primary_key=True, comment="版本ID (UUID)")
    pipeline_id = Column(String(64), nullable=False, index=True, comment="关联管道ID")
    tenant_id = Column(String(64), nullable=False, index=True, comment="租户ID（冗余）")
    version_number = Column(Integer, nullable=False, comment="版本号")
    change_log = Column(Text, comment="变更说明")
    config_snapshot = Column(Text, nullable=False, comment="管道配置完整快照 JSON")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
