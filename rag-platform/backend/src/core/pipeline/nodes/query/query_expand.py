"""查询扩展节点

LLM 调用生成扩展查询变体。
"""
from typing import Any

from src.core.pipeline.base_node import BaseNodeExecutor
from src.core.pipeline.node_context import NodeContext
from src.core.pipeline.node_result import NodeResult


class QueryExpandExecutor(BaseNodeExecutor):
    """查询扩展执行器"""

    @property
    def category(self) -> str:
        return "query"

    async def execute(self, context: NodeContext) -> NodeResult:
        """执行查询扩展"""
        query = context.input_data
        if not query:
            return NodeResult(output=[], node_id=context.node_id, node_type="query_expand")

        expansion_count = context.config.get("expansion_count", 3)

        # 简化实现：返回原查询
        variants = [query]

        return NodeResult(
            output=variants,
            metadata={"expansion_count": expansion_count},
            node_id=context.node_id,
            node_type="query_expand",
        )
