"""搜索请求实体类"""
from typing import Any, Optional

from pydantic import BaseModel, Field


class SearchParams(BaseModel):
    """搜索参数"""
    top_k: int = Field(default=10, ge=1, le=100, description="返回结果数量")
    temperature: float = Field(default=0.3, ge=0, le=1, description="LLM 温度")
    filters: dict[str, Any] = Field(default_factory=dict, description="额外过滤条件")
    max_domains: int = Field(default=5, ge=1, le=10, description="最大激活域数")
    response_top_k: Optional[int] = Field(
        default=None, ge=1, le=20, description="每个域展示的 top_chunks 数量限制"
    )


class PublishedUrlSearchRequest(BaseModel):
    """发布 URL 搜索请求（POST /search/{url_path}）"""
    query: str = Field(..., min_length=1, max_length=2000, description="查询文本")
    params: SearchParams = Field(default_factory=SearchParams, description="搜索参数")


class GenericSearchRequest(BaseModel):
    """通用端点搜索请求（POST /api/v1/search）"""
    pipeline_id: str = Field(..., description="管道ID")
    pipeline_version: Optional[int] = Field(default=None, description="管道版本（None 使用活动版本）")
    query: str = Field(..., min_length=1, max_length=2000, description="查询文本")
    params: SearchParams = Field(default_factory=SearchParams, description="搜索参数")


class StreamSearchRequest(BaseModel):
    """SSE 流式搜索请求（POST /api/v1/search/stream）"""
    pipeline_id: str = Field(..., description="管道ID")
    pipeline_version: Optional[int] = Field(default=None, description="管道版本")
    query: str = Field(..., min_length=1, max_length=2000, description="查询文本")
    params: SearchParams = Field(default_factory=SearchParams, description="搜索参数")
