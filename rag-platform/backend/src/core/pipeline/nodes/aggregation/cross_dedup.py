"""跨域去重节点

MinHash/embedding 跨域去重。
"""
from typing import Any

from src.core.pipeline.base_node import BaseNodeExecutor
from src.core.pipeline.node_context import NodeContext
from src.core.pipeline.node_result import NodeResult


class CrossDedupExecutor(BaseNodeExecutor):
    """跨域去重执行器"""

    @property
    def category(self) -> str:
        return "aggregation"

    async def execute(self, context: NodeContext) -> NodeResult:
        """执行跨域去重"""
        candidates = context.input_data
        if not candidates:
            return NodeResult(output=[], node_id=context.node_id, node_type="cross_dedup")

        threshold = context.config.get("dedup_threshold", 0.85)

        # 简化实现：不去重，直接返回
        return NodeResult(
            output=candidates,
            metadata={"threshold": threshold, "deduped_count": 0},
            node_id=context.node_id,
            node_type="cross_dedup",
        )
