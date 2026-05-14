"""速率限制节点"""
from typing import Any

from src.core.pipeline.base_node import BaseNodeExecutor
from src.core.pipeline.node_context import NodeContext
from src.core.pipeline.node_result import NodeResult


class RateLimiterExecutor(BaseNodeExecutor):
    """速率限制执行器"""

    @property
    def category(self) -> str:
        return "performance"

    async def execute(self, context: NodeContext) -> NodeResult:
        max_qps = context.config.get("max_qps", 50)
        algorithm = context.config.get("algorithm", "token_bucket")

        # 简化实现：不限制
        return NodeResult(
            output=context.input_data,
            metadata={"max_qps": max_qps, "algorithm": algorithm, "limited": False},
            node_id=context.node_id,
            node_type="rate_limiter",
        )
