"""分块相关实体类"""
from typing import Any, Optional

from pydantic import BaseModel, Field


class ChunkPreview(BaseModel):
    """分块预览"""
    chunk_index: int
    content: str
    char_count: int
    token_estimate: int
    metadata: Optional[dict[str, Any]] = None


class ChunkRead(BaseModel):
    """分块详情"""
    id: str
    kb_id: str
    doc_id: str
    chunk_index: int
    content: str
    token_count: Optional[int] = None
    metadata: Optional[dict[str, Any]] = None
    vector_id: Optional[str] = None

    model_config = {"from_attributes": True}


class ChunkPreviewResult(BaseModel):
    """分块预览结果"""
    total_chunks: int
    preview: list[ChunkPreview]
    strategy_config: dict[str, Any]
