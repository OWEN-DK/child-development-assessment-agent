"""幻觉检测节点"""
from typing import Any

from src.core.pipeline.base_node import BaseNodeExecutor
from src.core.pipeline.node_context import NodeContext
from src.core.pipeline.node_result import NodeResult


class HallucinationCheckExecutor(BaseNodeExecutor):
    """幻觉检测执行器"""

    @property
    def category(self) -> str:
        return "quality"

    async def execute(self, context: NodeContext) -> NodeResult:
        candidates = context.input_data
        threshold = context.config.get("threshold", 0.5)

        return NodeResult(
            output=candidates,
            metadata={"threshold": threshold},
            node_id=context.node_id,
            node_type="hallucination_check",
        )
