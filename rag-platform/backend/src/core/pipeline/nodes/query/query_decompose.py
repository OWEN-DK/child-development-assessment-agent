"""查询分解节点

LLM 调用拆解复杂查询为子查询。
"""
from typing import Any

from src.core.pipeline.base_node import BaseNodeExecutor
from src.core.pipeline.node_context import NodeContext
from src.core.pipeline.node_result import NodeResult
from src.utils.logger import logger


class QueryDecomposeExecutor(BaseNodeExecutor):
    """查询分解执行器"""

    @property
    def category(self) -> str:
        return "query"

    async def execute(self, context: NodeContext) -> NodeResult:
        """执行查询分解"""
        query = context.input_data
        if not query:
            return NodeResult(output=[], node_id=context.node_id, node_type="query_decompose")

        max_subqueries = context.config.get("max_subqueries", 5)

        # 简化实现：返回原查询作为唯一子查询
        # 实际实现应调用 LLM
        subqueries = [query]

        return NodeResult(
            output=subqueries,
            metadata={"max_subqueries": max_subqueries},
            node_id=context.node_id,
            node_type="query_decompose",
        )
