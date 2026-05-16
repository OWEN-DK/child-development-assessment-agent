"""知识库快照实体类"""
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


# ── 请求实体 ──────────────────────────────────────────

class CreateSnapshotReq(BaseModel):
    """创建知识库快照请求"""
    kb_id: str = Field(..., description="知识库ID")
    name: Optional[str] = Field(default=None, max_length=255, description="快照名称")


# ── 响应实体 ──────────────────────────────────────────

class SnapshotRead(BaseModel):
    """知识库快照读取"""
    id: str
    kb_id: str
    tenant_id: str
    name: Optional[str] = None
    vector_store_path: Optional[str] = None
    vector_backend_type: Optional[str] = None
    document_count: int = 0
    chunk_count: int = 0
    doc_ids_json: Optional[list[str]] = None
    chunk_strategy_json: Optional[dict[str, Any]] = None
    embedding_config_json: Optional[dict[str, Any]] = None
    config_snapshot: Optional[dict[str, Any]] = None
    status: str = "active"
    expires_at: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class SnapshotList(BaseModel):
    """知识库快照列表"""
    items: list[SnapshotRead]
    total: int
