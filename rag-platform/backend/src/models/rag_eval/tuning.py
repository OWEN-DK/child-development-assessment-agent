"""调优建议模型"""
from datetime import datetime

from sqlalchemy import JSON, Column, DateTime, Integer, String, Text

from src.models.base import Base


class TuningSuggestion(Base):
    """调优建议表"""
    __tablename__ = "tuning_suggestions"

    id = Column(String(64), primary_key=True, comment="建议ID")
    run_id = Column(String(64), nullable=False, index=True, comment="运行ID")
    report_id = Column(String(64), comment="报告ID")
    tenant_id = Column(String(64), nullable=False, index=True, comment="租户ID")
    category = Column(String(30), nullable=False, comment="分类：retrieval/generation/system/permission")
    severity = Column(String(20), nullable=False, comment="严重性：critical/warning/info")
    title = Column(String(255), nullable=False)
    description = Column(Text)
    current_value = Column(String(100))
    suggested_value = Column(String(100))
    expected_impact = Column(Text)
    source = Column(String(20), default="auto", comment="来源：auto/manual")
    priority = Column(Integer, default=5)
    safe_range = Column(String(100))
    conflict_with = Column(JSON, comment="冲突的建议ID列表")
    status = Column(String(20), nullable=False, default="pending", comment="状态：pending/adopted/rejected/ignored")
    applied_config_version_id = Column(String(64))
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
