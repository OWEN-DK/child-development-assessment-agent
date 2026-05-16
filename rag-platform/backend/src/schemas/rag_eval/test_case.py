"""测试用例实体类"""
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class DifficultyLevel(str, Enum):
    """难度等级"""
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


# ── 请求实体 ──────────────────────────────────────────

class CreateTestCaseReq(BaseModel):
    """创建测试用例请求"""
    query: str = Field(..., min_length=1, description="查询文本")
    description: Optional[str] = Field(default=None, max_length=500, description="用例描述")
    expected_knowledge_ids: list[str] = Field(default_factory=list, description="期望命中的知识片段ID列表")
    expected_keywords: list[str] = Field(default_factory=list, description="期望关键词")
    answer_points_summary: Optional[str] = Field(default=None, description="答案要点摘要")
    difficulty_level: DifficultyLevel = Field(default=DifficultyLevel.MEDIUM, description="难度等级")
    professional_terms: list[str] = Field(default_factory=list, description="专业术语列表")
    relevance_scores: dict[str, Any] = Field(default_factory=dict, description="相关性分数")
    relevant_domains: list[str] = Field(default_factory=list, description="期望激活的域列表")
    expected_conflicts: list[dict[str, Any]] = Field(default_factory=list, description="期望检测到的冲突")


class UpdateTestCaseReq(BaseModel):
    """更新测试用例请求（所有字段可选）"""
    query: Optional[str] = Field(default=None, min_length=1, description="查询文本")
    description: Optional[str] = Field(default=None, max_length=500, description="用例描述")
    expected_knowledge_ids: Optional[list[str]] = Field(default=None, description="期望命中的知识片段ID列表")
    expected_keywords: Optional[list[str]] = Field(default=None, description="期望关键词")
    answer_points_summary: Optional[str] = Field(default=None, description="答案要点摘要")
    difficulty_level: Optional[DifficultyLevel] = Field(default=None, description="难度等级")
    professional_terms: Optional[list[str]] = Field(default=None, description="专业术语列表")
    relevance_scores: Optional[dict[str, Any]] = Field(default=None, description="相关性分数")
    relevant_domains: Optional[list[str]] = Field(default=None, description="期望激活的域列表")
    expected_conflicts: Optional[list[dict[str, Any]]] = Field(default=None, description="期望检测到的冲突")


class ImportTestCaseReq(BaseModel):
    """批量导入测试用例请求"""
    cases: list[CreateTestCaseReq] = Field(..., min_length=1, description="待导入的用例列表")


class BatchDeleteCasesReq(BaseModel):
    """批量删除测试用例请求"""
    case_ids: list[str] = Field(..., min_length=1, description="待删除的用例ID列表")


# ── 响应实体 ──────────────────────────────────────────

class TestCaseRead(BaseModel):
    """测试用例读取"""
    id: str
    tenant_id: str
    query: str
    description: Optional[str] = None
    expected_knowledge_ids: Optional[list[str]] = None
    expected_keywords: Optional[list[str]] = None
    answer_points_summary: Optional[str] = None
    difficulty_level: str = "medium"
    professional_terms: Optional[list[str]] = None
    relevance_scores: Optional[dict[str, Any]] = None
    relevant_domains: Optional[list[str]] = None
    expected_conflicts: Optional[list[dict[str, Any]]] = None
    source: str = "manual"
    source_draft_id: Optional[str] = None
    version: int = 1
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TestCaseList(BaseModel):
    """测试用例列表"""
    items: list[TestCaseRead]
    total: int
