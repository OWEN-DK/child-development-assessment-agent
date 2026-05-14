"""域相关实体类"""
from typing import Any, Optional

from pydantic import BaseModel, Field


class DomainConfig(BaseModel):
    """域配置"""
    id: str
    name: str
    knowledge_base_id: str
    weight: float = 1.0
    activation_rules: dict[str, Any] = Field(default_factory=dict)
    pipeline: dict[str, Any] = Field(default_factory=dict)  # 域内管道配置


class DomainPlan(BaseModel):
    """域执行计划（查询分析输出）"""
    domain_id: str
    domain_name: str
    knowledge_base_id: str
    confidence: float = 0.0
    reason: str = ""


class DomainResult(BaseModel):
    """域执行结果"""
    domain_id: str
    domain_name: str
    candidates: list[dict[str, Any]] = Field(default_factory=list)
    contributed_to_answer: bool = True
    error: Optional[str] = None
