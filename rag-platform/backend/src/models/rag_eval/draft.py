"""测试用例草稿模型"""
from datetime import datetime

from sqlalchemy import JSON, Column, DateTime, Integer, Numeric, String, Text

from src.models.base import Base


class TestCaseDraft(Base):
    """测试用例草稿表"""
    __tablename__ = "test_case_drafts"

    id = Column(String(64), primary_key=True, comment="草稿ID")
    tenant_id = Column(String(64), nullable=False, index=True, comment="租户ID")
    query = Column(Text, nullable=False)
    description = Column(String(500))
    difficulty_level = Column(String(20), default="medium")
    expected_knowledge_ids = Column(JSON)
    expected_keywords = Column(JSON)
    answer_points = Column(Text)
    professional_terms = Column(JSON)
    source_document_id = Column(String(64))
    faithfulness_score = Column(Numeric(5, 4))
    status = Column(String(20), nullable=False, default="pending", comment="状态：pending/approved/rejected/imported")
    version = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
