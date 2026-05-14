"""迁移相关实体类"""
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

from .knowledge_base import VectorBackend


class MigrationStatus(str, Enum):
    """迁移状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


class MigrationRequest(BaseModel):
    """迁移请求"""
    target_backend: VectorBackend = Field(..., description="目标向量后端")


class MigrationEstimate(BaseModel):
    """迁移预估"""
    source_backend: VectorBackend
    target_backend: VectorBackend
    document_count: int
    chunk_count: int
    estimated_minutes: int
    warnings: list[str] = Field(default_factory=list)
