"""意图分类节点

LLM 调用分类查询意图。
"""
from typing import Any

from src.core.pipeline.base_node import BaseNodeExecutor
from src.core.pipeline.node_context import NodeContext
from src.core.pipeline.node_result import NodeResult


class IntentClassifyExecutor(BaseNodeExecutor):
    """意图分类执行器"""

    @property
    def category(self) -> str:
        return "query"

    async def execute(self, context: NodeContext) -> NodeResult:
        """执行意图分类"""
        query = context.input_data
        if not query:
            return NodeResult(output=[], node_id=context.node_id, node_type="intent_classify")

        categories = context.config.get("categories", [])

        # 简化实现：返回默认意图
        intents = [{"label": "general", "confidence": 1.0}]

        return NodeResult(
            output=intents,
            metadata={"categories": categories},
            node_id=context.node_id,
            node_type="intent_classify",
        )
