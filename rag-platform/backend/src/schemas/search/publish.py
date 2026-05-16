"""发布管理实体类"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class PublishConfig(BaseModel):
    """发布配置（输入）"""
    url_path: str = Field(
        ..., min_length=4, max_length=50,
        pattern=r"^[a-zA-Z0-9_-]+$",
        description="URL 路径（仅字母数字下划线连字符）",
    )
    bound_version: int = Field(..., ge=1, description="绑定的管道版本")
    http_method: str = Field(default="POST", pattern=r"^(POST|GET)$", description="HTTP 方法")
    auth_type: str = Field(default="jwt", pattern=r"^(jwt|api_key|none)$", description="认证类型")
    rate_limit: int = Field(default=0, ge=0, description="QPS 限制（0=不限）")
    enabled: bool = Field(default=True, description="是否启用")
    allowed_params: list[str] = Field(default_factory=list, description="允许的参数白名单")
    response_format: str = Field(default="json", pattern=r"^(json|sse|custom)$", description="响应格式")


class PublishResult(BaseModel):
    """发布结果（输出）"""
    endpoint_id: str = Field(description="端点ID")
    pipeline_id: str = Field(description="管道ID")
    url_path: str = Field(description="URL 路径")
    full_url: str = Field(default="", description="完整 URL")
    bound_version: int = Field(description="绑定版本")
    http_method: str = Field(description="HTTP 方法")
    auth_type: str = Field(description="认证类型")
    rate_limit: int = Field(description="QPS 限制")
    enabled: bool = Field(description="是否启用")
    allowed_params: list[str] = Field(default_factory=list, description="参数白名单")
    response_format: str = Field(description="响应格式")
    created_at: Optional[datetime] = Field(default=None)
    updated_at: Optional[datetime] = Field(default=None)


class PublishStatus(BaseModel):
    """发布状态"""
    published: bool = Field(description="是否已发布")
    endpoint_id: Optional[str] = Field(default=None)
    url_path: Optional[str] = Field(default=None)
    bound_version: Optional[int] = Field(default=None)
    active_version: Optional[int] = Field(default=None)
    version_behind: bool = Field(default=False, description="绑定版本是否落后于活动版本")
    enabled: bool = Field(default=False)


class EndpointItem(BaseModel):
    """端点列表项"""
    endpoint_id: str
    pipeline_id: str
    pipeline_name: str = Field(default="")
    url_path: str
    bound_version: int
    auth_type: str
    rate_limit: int
    enabled: bool
    call_count_24h: int = Field(default=0, description="24h 调用次数")
    avg_latency_ms_24h: float = Field(default=0.0, description="24h 平均延迟")
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class PaginatedEndpoints(BaseModel):
    """分页端点列表"""
    items: list[EndpointItem] = Field(default_factory=list)
    total: int = Field(default=0)
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class UnpublishResult(BaseModel):
    """停用结果"""
    pipeline_id: str
    url_path: str
    unpublished_at: datetime
