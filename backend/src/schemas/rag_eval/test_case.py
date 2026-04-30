"""测试用例 Schema"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict

from src.models.rag_eval.enums import DifficultyLevel, TestDomain


class TestCaseCreate(BaseModel):
    """测试用例创建请求"""

    query: str
    age: Optional[float] = None
    domain: Optional[TestDomain] = None
    description: Optional[str] = None
    expected_knowledge_ids: list[str] = []
    expected_keywords: list[str] = []
    answer_points_summary: Optional[str] = None
    difficulty_level: Optional[DifficultyLevel] = None


class TestCaseRead(TestCaseCreate):
    """测试用例读取"""

    id: str
    age_stage_label: str
    min_age_requirement: Optional[float] = None
    max_age_requirement: Optional[float] = None
    professional_terms: list[str] = []
    relevance_scores: Optional[dict[str, float]] = None
    source: str
    source_draft_id: Optional[str] = None
    source_document_id: Optional[str] = None
    version: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TestCaseUpdate(BaseModel):
    """测试用例更新"""

    query: Optional[str] = None
    age: Optional[float] = None
    domain: Optional[TestDomain] = None
    description: Optional[str] = None
    expected_knowledge_ids: Optional[list[str]] = None
    expected_keywords: Optional[list[str]] = None
    answer_points_summary: Optional[str] = None
    difficulty_level: Optional[DifficultyLevel] = None


class TestCaseList(BaseModel):
    """测试用例分页列表"""

    items: list[TestCaseRead]
    total: int
    page: int
    page_size: int


class TestCaseImportItem(BaseModel):
    """单个导入项，字段比 TestCaseCreate 更宽松"""

    query: str
    age: Optional[float] = None  # 岁，如 1.5
    domain: Optional[str] = None  # 字符串，校验时转为 TestDomain
    description: Optional[str] = None
    expected_knowledge_ids: list[str] = []
    expected_keywords: list[str] = []
    answer_points_summary: Optional[str] = None
    difficulty_level: Optional[str] = None  # 校验时转为 DifficultyLevel


class TestCaseImportData(BaseModel):
    """批量导入请求"""

    cases: list[TestCaseImportItem]
