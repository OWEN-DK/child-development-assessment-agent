"""敏感词过滤节点"""
from typing import Any

from src.core.pipeline.base_node import BaseNodeExecutor
from src.core.pipeline.node_context import NodeContext
from src.core.pipeline.node_result import NodeResult


class SensitiveFilterExecutor(BaseNodeExecutor):
    """敏感词过滤执行器"""

    @property
    def category(self) -> str:
        return "security"

    async def execute(self, context: NodeContext) -> NodeResult:
        candidates = context.input_data
        word_list = context.config.get("word_list", [])
        filter_mode = context.config.get("filter_mode", "remove")

        # 简化实现：不过滤
        return NodeResult(
            output=candidates,
            metadata={"word_list_count": len(word_list), "filter_mode": filter_mode},
            node_id=context.node_id,
            node_type="sensitive_filter",
        )
