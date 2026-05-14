"""术语标准化节点

查术语映射表替换非标准术语。
"""
from typing import Any

from src.core.pipeline.base_node import BaseNodeExecutor
from src.core.pipeline.node_context import NodeContext
from src.core.pipeline.node_result import NodeResult


class TermNormalizeExecutor(BaseNodeExecutor):
    """术语标准化执行器"""

    @property
    def category(self) -> str:
        return "query"

    async def execute(self, context: NodeContext) -> NodeResult:
        """执行术语标准化"""
        query = context.input_data
        if not query:
            return NodeResult(output="", node_id=context.node_id, node_type="term_normalize")

        # 简化实现：返回原查询
        return NodeResult(
            output=query,
            metadata={},
            node_id=context.node_id,
            node_type="term_normalize",
        )
