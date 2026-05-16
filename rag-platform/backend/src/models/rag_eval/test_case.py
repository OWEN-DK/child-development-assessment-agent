"""测试用例模型"""
from datetime import datetime

from sqlalchemy import JSON, Column, DateTime, Integer, String, Text

from src.models.base import Base


class TestCase(Base):
    """测试用例表"""
    __tablename__ = "test_cases"

    id = Column(String(64), primary_key=True, comment="用例ID")
    tenant_id = Column(String(64), nullable=False, index=True, comment="租户ID")
    query = Column(Text, nullable=False, comment="查询文本")
    description = Column(String(500), comment="用例描述")
    expected_knowledge_ids = Column(JSON, comment="期望命中的知识片段ID列表")
    expected_keywords = Column(JSON, comment="期望关键词")
    answer_points_summary = Column(Text, comment="答案要点摘要")
    difficulty_level = Column(String(20), default="medium", comment="难度：easy/medium/hard")
    professional_terms = Column(JSON, comment="专业术语列表")
    relevance_scores = Column(JSON, comment="相关性分数")
    relevant_domains = Column(JSON, comment="期望激活的域列表")
    expected_conflicts = Column(JSON, comment="期望检测到的冲突")
    source = Column(String(20), default="manual", comment="来源：manual/import/draft")
    source_draft_id = Column(String(64), comment="来源草稿ID")
    version = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class TestSet(Base):
    """测试集表"""
    __tablename__ = "test_sets"

    id = Column(String(64), primary_key=True, comment="测试集ID")
    tenant_id = Column(String(64), nullable=False, index=True, comment="租户ID")
    name = Column(String(255), nullable=False, comment="测试集名称")
    description = Column(Text, comment="描述")
    source_type = Column(String(20), default="manual", comment="来源：manual/import/search_history")
    case_ids = Column(JSON, comment="关联的用例ID列表（有序）")
    visibility = Column(String(20), default="public", comment="可见性")
    owner_id = Column(String(64), nullable=False, comment="创建者ID")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class TestSetCase(Base):
    """测试集用例关联表"""
    __tablename__ = "test_set_cases"

    set_id = Column(String(64), primary_key=True, comment="测试集ID")
    case_id = Column(String(64), primary_key=True, comment="用例ID")
    sort_order = Column(Integer, nullable=False, default=0, comment="排序序号")
