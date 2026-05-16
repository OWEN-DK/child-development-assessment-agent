"""评估报告模型"""
from datetime import datetime

from sqlalchemy import JSON, Column, DateTime, Numeric, String, Text

from src.models.base import Base


class EvalReport(Base):
    """评估报告表"""
    __tablename__ = "eval_reports"

    id = Column(String(64), primary_key=True, comment="报告ID")
    run_id = Column(String(64), nullable=False, index=True, comment="运行ID")
    tenant_id = Column(String(64), nullable=False, index=True, comment="租户ID")
    overall_score = Column(Numeric(5, 4))
    l1_score = Column(Numeric(5, 4))
    l2_score = Column(Numeric(5, 4))
    l3_score = Column(Numeric(5, 4))
    cross_domain_score = Column(Numeric(5, 4))
    metrics_json = Column(JSON)
    diagnosis_json = Column(JSON)
    bad_cases_json = Column(JSON)
    suggestions_json = Column(JSON)
    cross_domain_json = Column(JSON)
    markdown_content = Column(Text, comment="Markdown 报告内容")
    status = Column(String(20), nullable=False, default="processing", comment="状态：processing/completed/superseded")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
