"""草稿 Schema"""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from src.models.rag_eval.enums import DifficultyLevel


class DraftCreate(BaseModel):
    """草稿创建请求"""

    query: str
    description: Optional[str] = None
    expected_knowledge_ids: list[str] = Field(default_factory=list)
    expected_keywords: list[str] = Field(default_factory=list)
    answer_points: Optional[list[str]] = None
    professional_terms: list[str] = Field(default_factory=list)
    difficulty_level: Optional[DifficultyLevel] = None
    source_chunk_id: Optional[str] = None
    source_page: Optional[int] = None
    source_content_snippet: Optional[str] = None
    generation_params: Optional[dict] = None


class DraftRead(DraftCreate):
    """草稿读取"""

    id: str
    source_document_id: Optional[str] = None
    status: str
    version: int
    faithfulness_score: Optional[float] = None
    batch_id: Optional[str] = None
    draft_index: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DraftUpdate(BaseModel):
    """草稿更新"""

    query: Optional[str] = None
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


class BookMetadata(BaseModel):
    """文档元数据分析结果"""

    topic_summary: str = ""
