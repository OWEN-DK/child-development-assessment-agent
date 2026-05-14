"""冲突检测节点

LLM 调用检测跨域矛盾表述。
"""
from typing import Any

from src.core.pipeline.base_node import BaseNodeExecutor
from src.core.pipeline.node_context import NodeContext
from src.core.pipeline.node_result import NodeResult


class ConflictDetectExecutor(BaseNodeExecutor):
    """冲突检测执行器"""

    @property
    def category(self) -> str:
        return "aggregation"

    async def execute(self, context: NodeContext) -> NodeResult:
        """执行冲突检测"""
        candidates = context.input_data
        enabled = context.config.get("enabled", True)

        if not enabled or not candidates:
            return NodeResult(
                output={"conflicts": [], "has_conflicts": False},
                node_id=context.node_id,
                node_type="conflict_detect",
            )

        # 实际实现应调用 LLM 检测矛盾
        conflict_report = {
            "conflicts": [],
            "has_conflicts": False,
        }

        return NodeResult(
            output=conflict_report,
            metadata={"enabled": enabled},
            node_id=context.node_id,
            node_type="conflict_detect",
        )
