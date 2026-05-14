"""重排序节点"""
from typing import Any

from src.core.pipeline.base_node import BaseNodeExecutor
from src.core.pipeline.node_context import NodeContext
from src.core.pipeline.node_result import NodeResult


class RerankExecutor(BaseNodeExecutor):
    """重排序执行器"""

    @property
    def category(self) -> str:
        return "quality"

    async def execute(self, context: NodeContext) -> NodeResult:
        candidates = context.input_data
        if not candidates:
            return NodeResult(output=[], node_id=context.node_id, node_type="rerank")

        final_k = context.config.get("final_k", 5)

        # 简化实现：截取前 final_k 个
        result = candidates[:final_k] if isinstance(candidates, list) else candidates

        return NodeResult(
            output=result,
            metadata={"final_k": final_k},
            node_id=context.node_id,
            node_type="rerank",
        )
