"""同义词扩展节点

查同义词库扩展查询词。
"""
from typing import Any

from src.core.pipeline.base_node import BaseNodeExecutor
from src.core.pipeline.node_context import NodeContext
from src.core.pipeline.node_result import NodeResult
from src.utils.logger import logger


class SynonymExpandExecutor(BaseNodeExecutor):
    """同义词扩展执行器"""

    @property
    def category(self) -> str:
        return "query"

    async def execute(self, context: NodeContext) -> NodeResult:
        """执行同义词扩展"""
        query = context.input_data
        if not query:
            return NodeResult(output="", node_id=context.node_id, node_type="synonym_expand")

        max_synonyms = context.config.get("max_synonyms", 5)

        # 简化实现：返回原查询
        # 实际实现应查同义词库
        expanded = query

        return NodeResult(
            output=expanded,
            metadata={"max_synonyms": max_synonyms},
            node_id=context.node_id,
            node_type="synonym_expand",
        )
