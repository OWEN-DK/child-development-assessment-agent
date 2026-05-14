"""边相关实体类"""
from typing import Any, Optional

from pydantic import BaseModel, Field


class EdgeConfig(BaseModel):
    """边配置"""
    id: str
    source: str  # 源节点 ID
    target: str  # 目标节点 ID
    type: str = "data"  # data / conditional / degradation


class ConditionalEdgeConfig(EdgeConfig):
    """条件边配置"""
    type: str = "conditional"
    condition: str = ""  # 条件表达式
    condition_type: str = ""  # cache_hit / cache_miss / intent_route


class DegradationEdgeConfig(EdgeConfig):
    """降级边配置"""
    type: str = "degradation"
    strategy: str = "skip_node"  # skip_node / reroute / degrade_cache / abort
    alternate_node_id: Optional[str] = None  # reroute 时的备选节点
