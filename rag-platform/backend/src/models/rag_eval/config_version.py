"""评估配置版本模型"""
from datetime import datetime

from sqlalchemy import JSON, Column, DateTime, Integer, String, Text

from src.models.base import Base


class EvalConfigVersion(Base):
    """评估配置版本表"""
    __tablename__ = "eval_config_versions"

    id = Column(String(64), primary_key=True, comment="配置版本ID")
    tenant_id = Column(String(64), nullable=False, index=True, comment="租户ID")
    version_number = Column(Integer, nullable=False, comment="版本号")
    version_label = Column(String(100))
    config_snapshot = Column(JSON, nullable=False, comment="配置快照")
    change_summary = Column(Text)
    change_set_id = Column(String(64))
    created_by = Column(String(64), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class EvalConfigChangeSet(Base):
    """评估配置变更集表"""
    __tablename__ = "eval_config_change_sets"

    id = Column(String(64), primary_key=True, comment="变更集ID")
    tenant_id = Column(String(64), nullable=False, index=True, comment="租户ID")
    change_set_label = Column(String(255))
    config_version_id = Column(String(64), nullable=False)
    previous_version_id = Column(String(64))
    status = Column(String(20), nullable=False, default="committed", comment="状态：committed/rolled_back")
    rollback_reason = Column(Text)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
