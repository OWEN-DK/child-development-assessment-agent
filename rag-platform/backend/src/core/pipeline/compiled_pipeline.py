"""编译后的管道数据结构

ExecutionPlan、PipelineState、CompiledPipeline 等核心数据类型。
从 compiler.py 拆分出来以保持单类 ≤ 500 行限制。
"""
from dataclasses import dataclass, field
from typing import Any

from src.core.pipeline.node_context import AuthContext


@dataclass
class PlanNode:
    """执行计划节点"""
    node_id: str
    node_type: str
    config: dict[str, Any] = field(default_factory=dict)
    domain_id: str = ""
    knowledge_base_id: str = ""
    depends_on: list[str] = field(default_factory=list)
    downstream: list[str] = field(default_factory=list)
    is_aggregation: bool = False
    degradation_strategies: list[str] = field(default_factory=list)
    alternate_node_id: str = ""


@dataclass
class ExecutionPlan:
    """执行计划"""
    nodes: dict[str, PlanNode] = field(default_factory=dict)
    sorted_ids: list[str] = field(default_factory=list)
    parallel_groups: list[list[str]] = field(default_factory=list)
    conditional_routes: dict[str, dict[str, str]] = field(default_factory=dict)
    degradation_routes: dict[str, dict[str, Any]] = field(default_factory=dict)
    # 域管道：domain_id → 域内节点拓扑排序列表
    domain_plans: dict[str, list[str]] = field(default_factory=dict)


@dataclass
class PipelineState:
    """管道执行状态"""
    query: str = ""
    params: dict[str, Any] = field(default_factory=dict)
    auth: AuthContext = field(default_factory=lambda: AuthContext(tenant_id="", user_id=""))

    # 所有节点的输出（node_id → output）
    node_outputs: dict[str, Any] = field(default_factory=dict)

    # 域执行结果
    domain_results: list[dict[str, Any]] = field(default_factory=list)

    # 最终结果
    answer: str = ""
    sources: list[dict[str, Any]] = field(default_factory=list)

    # 快捷路径
    shortcut_activated: bool = False

    # 降级事件
    degradation_events: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class CompiledPipeline:
    """编译后的管道"""
    config: dict[str, Any] = field(default_factory=dict)
    execution_plan: ExecutionPlan = field(default_factory=ExecutionPlan)
    domain_configs: list[dict[str, Any]] = field(default_factory=list)
    aggregation_config: dict[str, Any] = field(default_factory=dict)
