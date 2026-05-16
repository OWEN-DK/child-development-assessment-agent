"""测试用例草稿实体类"""
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

from src.schemas.rag_eval.test_case import DifficultyLevel


class DraftStatus(str, Enum):
    """草稿状态"""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    IMPORTED = "imported"


class ReviewAction(str, Enum):
    """审核动作"""
    APPROVE = "approve"
    REJECT = "reject"


# ── 请求实体 ──────────────────────────────────────────

class CreateDraftReq(BaseModel):
    """创建草稿请求"""
    query: str = Field(..., min_length=1, description="查询文本")
    description: Optional[str] = Field(default=None, max_length=500, description="用例描述")
    difficulty_level: DifficultyLevel = Field(default=DifficultyLevel.MEDIUM, description="难度等级")
    expected_knowledge_ids: list[str] = Field(default_factory=list, description="期望命中的知识片段ID列表")
    expected_keywords: list[str] = Field(default_factory=list, description="期望关键词")
    answer_points: Optional[str] = Field(default=None, description="答案要点")
    professional_terms: list[str] = Field(default_factory=list, description="专业术语列表")
    source_document_id: Optional[str] = Field(default=None, description="来源文档ID")
    faithfulness_score: Optional[float] = Field(default=None, ge=0, le=1, description="忠实度分数")


class GenerateDraftReq(BaseModel):
    """批量生成草稿请求"""
    kb_id: str = Field(..., description="知识库ID")
    document_ids: list[str] = Field(..., min_length=1, description="文档ID列表")
    max_qa_per_chunk: int = Field(default=3, ge=1, le=10, description="每块最大生成问答数")
    min_qa_per_chunk: int = Field(default=1, ge=1, le=10, description="每块最小生成问答数")


class ReviewDraftReq(BaseModel):
    """审核草稿请求"""
    action: ReviewAction = Field(..., description="审核动作：approve/reject")


class UpdateDraftReq(BaseModel):
    """更新草稿请求（部分字段可选）"""
    query: Optional[str] = Field(default=None, min_length=1, description="查询文本")
    description: Optional[str] = Field(default=None, max_length=500, description="用例描述")
    difficulty_level: Optional[DifficultyLevel] = Field(default=None, description="难度等级")
    expected_knowledge_ids: Optional[list[str]] = Field(default=None, description="期望命中的知识片段ID列表")
    expected_keywords: Optional[list[str]] = Field(default=None, description="期望关键词")
    answer_points: Optional[str] = Field(default=None, description="答案要点")
    professional_terms: Optional[list[str]] = Field(default=None, description="专业术语列表")


# ── 响应实体 ──────────────────────────────────────────

class DraftRead(BaseModel):
    """草稿读取"""
    id: str
    tenant_id: str
    query: str
    description: Optional[str] = None
    difficulty_level: str = "medium"
    expected_knowledge_ids: Optional[list[str]] = None
    expected_keywords: Optional[list[str]] = None
    answer_points: Optional[str] = None
    professional_terms: Optional[list[str]] = None
    source_document_id: Optional[str] = None
    faithfulness_score: Optional[float] = None
    status: DraftStatus = DraftStatus.PENDING
    version: int = 1
    created_at: datetime

    model_config = {"from_attributes": True}


class DraftList(BaseModel):
    """草稿列表"""
    items: list[DraftRead]
    total: int
