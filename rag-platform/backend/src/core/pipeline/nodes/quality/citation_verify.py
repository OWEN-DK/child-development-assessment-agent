"""引用验证节点"""
from typing import Any

from src.core.pipeline.base_node import BaseNodeExecutor
from src.core.pipeline.node_context import NodeContext
from src.core.pipeline.node_result import NodeResult


class CitationVerifyExecutor(BaseNodeExecutor):
    """引用验证执行器"""

    @property
    def category(self) -> str:
        return "quality"

    async def execute(self, context: NodeContext) -> NodeResult:
        candidates = context.input_data
        mode = context.config.get("mode", "lax")

        return NodeResult(
            output=candidates,
            metadata={"mode": mode},
            node_id=context.node_id,
            node_type="citation_verify",
        )
