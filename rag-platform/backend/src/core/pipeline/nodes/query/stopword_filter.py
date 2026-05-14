"""禁用词过滤节点

正则/列表匹配移除禁用词。
"""
import re
from typing import Any

from src.core.pipeline.base_node import BaseNodeExecutor
from src.core.pipeline.node_context import NodeContext
from src.core.pipeline.node_result import NodeResult


class StopwordFilterExecutor(BaseNodeExecutor):
    """禁用词过滤执行器"""

    @property
    def category(self) -> str:
        return "query"

    async def execute(self, context: NodeContext) -> NodeResult:
        """执行禁用词过滤"""
        query = context.input_data
        if not query:
            return NodeResult(output="", node_id=context.node_id, node_type="stopword_filter")

        enabled = context.config.get("enabled", False)
        if not enabled:
            return NodeResult(output=query, node_id=context.node_id, node_type="stopword_filter")

        stop_words = context.config.get("stop_words", [])
        case_sensitive = context.config.get("case_sensitive", False)

        filtered = query
        for word in stop_words:
            if case_sensitive:
                filtered = filtered.replace(word, "")
            else:
                pattern = re.compile(re.escape(word), re.IGNORECASE)
                filtered = pattern.sub("", filtered)

        return NodeResult(
            output=filtered.strip(),
            metadata={"removed_count": len(stop_words)},
            node_id=context.node_id,
            node_type="stopword_filter",
        )
