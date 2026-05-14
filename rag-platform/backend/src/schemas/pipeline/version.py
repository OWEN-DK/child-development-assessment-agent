"""管道版本相关实体类"""
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class PipelineVersionRead(BaseModel):
    """版本详情"""
    id: str
    pipeline_id: str
    version_number: int
    change_log: Optional[str] = None
    config_snapshot: dict[str, Any]
    created_at: datetime

    model_config = {"from_attributes": True}


class PipelineVersionListItem(BaseModel):
    """版本列表项"""
    id: str
    version_number: int
    change_log: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class VersionCompareResult(BaseModel):
    """版本对比结果"""
    v1: int
    v2: int
    added_nodes: list[str] = Field(default_factory=list)
    removed_nodes: list[str] = Field(default_factory=list)
    modified_nodes: list[dict[str, Any]] = Field(default_factory=list)
    added_edges: list[str] = Field(default_factory=list)
    removed_edges: list[str] = Field(default_factory=list)
    param_changes: list[dict[str, Any]] = Field(default_factory=list)
