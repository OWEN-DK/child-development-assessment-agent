"""复合节点相关实体类"""
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class CompoundNodeCreate(BaseModel):
    """创建复合节点请求"""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    expanded_nodes: list[dict[str, Any]] = Field(default_factory=list)
    internal_edges: list[dict[str, Any]] = Field(default_factory=list)
    exposed_ports: dict[str, list[str]] = Field(default_factory=dict)  # {input: [...], output: [...]}


class CompoundNodeRead(BaseModel):
    """复合节点详情"""
    id: str
    name: str
    description: Optional[str] = None
    node_count: int = 0
    is_shared: bool = False
    created_at: datetime

    model_config = {"from_attributes": True}


class CompoundNodeImport(BaseModel):
    """导入复合节点"""
    data: dict[str, Any]
