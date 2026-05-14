"""结构化输出节点"""
from typing import Any

from src.core.pipeline.base_node import BaseNodeExecutor
from src.core.pipeline.node_context import NodeContext
from src.core.pipeline.node_result import NodeResult


class StructuredOutputExecutor(BaseNodeExecutor):
    """结构化输出执行器"""

    @property
    def category(self) -> str:
        return "synthesis"

    async def execute(self, context: NodeContext) -> NodeResult:
        candidates = context.input_data
        output_format = context.config.get("output_format", "json")
        model = context.config.get("model", "qwen-turbo")

        # 简化实现：返回原始数据
        return NodeResult(
            output=candidates,
            metadata={"output_format": output_format, "model": model},
            node_id=context.node_id,
            node_type="structured_output",
        )
