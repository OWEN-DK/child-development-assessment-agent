"""搜索响应实体类"""
from typing import Any, Optional

from pydantic import BaseModel, Field


class TopChunk(BaseModel):
    """检索结果片段"""
    chunk_id: str = Field(description="分块ID")
    doc_name: str = Field(default="", description="文档名称")
    text: str = Field(description="文本内容")
    score: float = Field(description="相关性分数")
    metadata: dict[str, Any] = Field(default_factory=dict, description="额外元数据")


class DomainResult(BaseModel):
    """域检索结果"""
    domain_id: str = Field(description="域ID")
    domain_name: str = Field(default="", description="域名称")
    candidates: list[dict[str, Any]] = Field(default_factory=list, description="原始候选集")
    top_chunks: list[TopChunk] = Field(default_factory=list, description="展示用 top 片段")
    contributed_to_answer: bool = Field(default=False, description="是否贡献了答案")
    error: Optional[str] = Field(default=None, description="错误信息")


class ConflictInfo(BaseModel):
    """冲突信息"""
    type: str = Field(default="contradiction", description="冲突类型")
    statement_a: str = Field(description="矛盾表述 A")
    source_a: str = Field(default="", description="来源 A")
    statement_b: str = Field(description="矛盾表述 B")
    source_b: str = Field(default="", description="来源 B")
    resolution: str = Field(default="", description="解决方式")


class PipelineTrace(BaseModel):
    """管道执行追踪"""
    pipeline_id: str = Field(description="管道ID")
    pipeline_version: int = Field(description="管道版本")
    total_latency_ms: int = Field(description="总耗时（毫秒）")
    domain_parallel_latency_ms: int = Field(default=0, description="域并行耗时")
    aggregation_latency_ms: int = Field(default=0, description="聚合层耗时")


class DegradationEvent(BaseModel):
    """降级事件"""
    node_id: str = Field(description="节点ID")
    node_type: str = Field(default="", description="节点类型")
    domain_id: str = Field(default="", description="域ID")
    strategy: str = Field(description="降级策略：skip_node/reroute/degrade_cache/abort")
    reason: str = Field(default="", description="降级原因")


class SearchResponse(BaseModel):
    """搜索响应"""
    run_id: str = Field(description="运行ID")
    answer: str = Field(default="", description="生成的答案")
    shortcut_activated: bool = Field(default=False, description="是否触发单域快捷路径")
    filtered_domains: int = Field(default=0, description="被权限裁剪的域数量")
    domain_results: list[DomainResult] = Field(default_factory=list, description="各域检索结果")
    conflicts: list[ConflictInfo] = Field(default_factory=list, description="跨域冲突")
    pipeline_trace: Optional[PipelineTrace] = Field(default=None, description="管道执行追踪")
    degradation_events: list[DegradationEvent] = Field(default_factory=list, description="降级事件")
    truncated: bool = Field(default=False, description="响应是否被截断（>2MB）")
