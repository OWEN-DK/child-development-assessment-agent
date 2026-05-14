"""节点执行结果"""
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class NodeResult:
    """节点执行结果

    包含输出数据和元信息（是否降级、降级策略等）。
    """
    # 输出数据
    output: Any = None

    # 元信息
    metadata: dict[str, Any] = field(default_factory=dict)

    # 降级信息
    degraded: bool = False
    degradation_strategy: Optional[str] = None  # skip_node / reroute / degrade_cache / abort
    degradation_reason: Optional[str] = None

    # 执行信息
    execution_time_ms: int = 0
    node_id: str = ""
    node_type: str = ""

    @property
    def is_empty(self) -> bool:
        """输出是否为空"""
        if self.output is None:
            return True
        if isinstance(self.output, (list, dict)) and len(self.output) == 0:
            return True
        return False
