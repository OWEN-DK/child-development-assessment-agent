"""统一答案合成节点

LLM 调用综合多域结果生成最终答案。
"""
from typing import Any

from src.core.pipeline.base_node import BaseNodeExecutor
from src.core.pipeline.node_context import NodeContext
from src.core.pipeline.node_result import NodeResult
from src.utils.logger import logger


class UnifiedGenerateExecutor(BaseNodeExecutor):
    """统一答案合成执行器"""

    @property
    def category(self) -> str:
        return "aggregation"

    async def execute(self, context: NodeContext) -> NodeResult:
        """执行统一答案合成"""
        input_data = context.input_data
        if not input_data:
            return NodeResult(
                output="",
                node_id=context.node_id,
                node_type="unified_generate",
            )

        model = context.config.get("model", "qwen-turbo")
        temperature = context.config.get("temperature", 0.3)
        max_tokens = context.config.get("max_tokens", 2048)
        include_citations = context.config.get("include_citations", True)

        # 实际实现应调用 LLM 生成答案
        # 简化实现
        answer = "（答案生成占位）"

        return NodeResult(
            output=answer,
            metadata={
                "model": model,
                "temperature": temperature,
                "include_citations": include_citations,
            },
            node_id=context.node_id,
            node_type="unified_generate",
        )
