"""去重节点"""
from typing import Any

from src.core.pipeline.base_node import BaseNodeExecutor
from src.core.pipeline.node_context import NodeContext
from src.core.pipeline.node_result import NodeResult


class DedupExecutor(BaseNodeExecutor):
    """去重执行器"""

    @property
    def category(self) -> str:
        return "quality"

    async def execute(self, context: NodeContext) -> NodeResult:
        candidates = context.input_data
        if not candidates:
            return NodeResult(output=[], node_id=context.node_id, node_type="dedup")

        threshold = context.config.get("threshold", 0.85)
        method = context.config.get("method", "minhash")

        # 简化实现：不去重
        return NodeResult(
            output=candidates,
            metadata={"method": method, "threshold": threshold},
            node_id=context.node_id,
            node_type="dedup",
        )
