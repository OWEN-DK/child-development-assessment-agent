"""节点执行上下文

包含节点执行所需的全部信息：输入数据、配置、认证上下文、追踪信息。
"""
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class AuthContext:
    """认证上下文"""
    tenant_id: str
    user_id: str
    roles: list[str] = field(default_factory=list)
    is_superadmin: bool = False
    is_god_mode: bool = False


@dataclass
class NodeContext:
    """节点执行上下文

    每个节点执行时接收此上下文，包含所有必要信息。
    """
    # 输入数据
    input_data: Any = None

    # 节点配置（合并后的最终配置）
    config: dict[str, Any] = field(default_factory=dict)

    # 认证上下文
    auth: AuthContext = field(default_factory=lambda: AuthContext(tenant_id="", user_id=""))

    # 管道标识
    pipeline_id: str = ""
    pipeline_version: int = 0

    # 域标识（域内节点才有）
    domain_id: str = ""
    domain_name: str = ""
    knowledge_base_id: str = ""

    # 节点标识
    node_id: str = ""
    node_type: str = ""

    # 追踪
    trace_id: str = ""
    parent_span_id: str = ""

    # 扩展字段
    metadata: dict[str, Any] = field(default_factory=dict)
