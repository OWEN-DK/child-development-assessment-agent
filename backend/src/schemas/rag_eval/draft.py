"""草稿 Schema"""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict

from src.models.rag_eval.enums import DifficultyLevel, TestDomain


class DraftCreate(BaseModel):
    """草稿创建请求"""

    query: str
    age: float
    age_stage_label: str = ""
    domain: TestDomain
    description: Optional[str] = None
    expected_knowledge_ids: list[str] = []
    expected_keywords: list[str] = []
    answer_points: list[str] = []
    professional_terms: list[str] = []
    difficulty_level: Optional[DifficultyLevel] = None
    source_chunk_id: Optional[str] = None
    source_page: Optional[int] = None
    source_content_snippet: Optional[str] = None
    generation_params: Optional[dict] = None


class DraftRead(DraftCreate):
    """草稿读取"""

    id: str
    status: str
    version: int
    faithfulness_score: float
    batch_id: str
    draft_index: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DraftUpdate(BaseModel):
    """草稿更新"""

    query: Optional[str] = None
    age: Optional[float] = None
    age_stage_label: Optional[str] = None
    domain: Optional[TestDomain] = None
    description: Optional[str] = None
    expected_knowledge_ids: Optional[list[str]] = None
    expected_keywords: Optional[list[str]] = None
    answer_points: Optional[list[str]] = None
    professional_terms: Optional[list[str]] = None
    difficulty_level: Optional[DifficultyLevel] = None
    source_chunk_id: Optional[str] = None
    source_page: Optional[int] = None
    source_content_snippet: Optional[str] = None


class DraftReview(BaseModel):
    """草稿审核操作"""

    action: Literal["approve", "reject"]
    review_comment: Optional[str] = None


class DraftList(BaseModel):
    """草稿分页列表"""

    items: list[DraftRead]
    total: int
    page: int
    page_size: int


class DraftGenerationConfig(BaseModel):
    """草稿生成配置"""

    max_qa_per_chunk: int = 3
    min_qa_per_chunk: int = 1
    custom_age_ranges: Optional[list[tuple[float, float]]] = None  # 覆盖自动检测的年龄范围
    custom_domains: Optional[list[str]] = None  # 覆盖自动检测的测试领域


class BookMetadata(BaseModel):
    """文档元数据分析结果"""

    age_ranges: list[tuple[float, float]]  # [(min_age, max_age), ...]
    domains: list[str]  # TestDomain 值列表
    difficulty_hint: Optional[str] = None  # easy/medium/hard
    topic_summary: str = ""
