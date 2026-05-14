"""管道相关实体类"""
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class PipelineCreate(BaseModel):
    """创建管道请求"""
    name: str = Field(..., min_length=1, max_length=255, description="管道名称")
    description: Optional[str] = Field(default=None, description="管道描述")
    type: str = Field(default="aggregation", description="管道类型")


class PipelineUpdate(BaseModel):
    """更新管道请求"""
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    description: Optional[str] = None
    status: Optional[str] = None
    config: Optional[dict[str, Any]] = Field(default=None, description="管道配置（触发版本递增）")
    change_log: Optional[str] = Field(default=None, description="变更说明")


class PipelineRead(BaseModel):
    """管道详情"""
    id: str
    tenant_id: str
    name: str
    description: Optional[str] = None
    type: str = "aggregation"
    active_version: int = 1
    status: str = "draft"
    domain_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PipelineList(BaseModel):
    """管道列表"""
    items: list[PipelineRead]
    total: int


class PipelineConfig(BaseModel):
    """管道完整配置"""
    pipeline: dict[str, Any]
    domains: list[dict[str, Any]] = Field(default_factory=list)
    aggregation: dict[str, Any] = Field(default_factory=dict)
