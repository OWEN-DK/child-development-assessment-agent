"""知识库快照 Schema"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class SnapshotCreate(BaseModel):
    """快照创建请求"""

    name: Optional[str] = None
    description: str = ""


class SnapshotRead(BaseModel):
    """快照读取"""

    id: str
    name: str
    description: str
    vector_store_path: str
    document_count: int
    chunk_count: int
    config_version_id: Optional[str] = None
    config_snapshot: Optional[dict] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
