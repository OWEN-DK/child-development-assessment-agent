"""查询改写节点

LLM 调用改写查询，输出查询变体列表。
"""
from typing import Any

from src.core.pipeline.base_node import BaseNodeExecutor
from src.core.pipeline.node_context import NodeContext
from src.core.pipeline.node_result import NodeResult
from src.utils.logger import logger


class QueryRewriteExecutor(BaseNodeExecutor):
    """查询改写执行器"""

    @property
    def category(self) -> str:
        return "query"

    @property
    def input_type(self) -> str:
        return "str"

    @property
    def output_type(self) -> str:
        return "list[str]"

    async def execute(self, context: NodeContext) -> NodeResult:
        """执行查询改写"""
        query = context.input_data
        if not query:
            return NodeResult(output=[], node_id=context.node_id, node_type="query_rewrite")

        model = context.config.get("model", "qwen-turbo")
        prompt_template = context.config.get(
            "prompt_template",
            "请将以下查询改写为更适合检索的形式，保持语义不变：\n{query}"
        )

        # 简化实现：直接返回原查询作为变体
        # 实际实现应调用 LLM
        variants = [query]

        logger.debug(f"查询改写: {query} → {len(variants)} 个变体")

        return NodeResult(
            output=variants,
            metadata={"original_query": query, "model": model},
            node_id=context.node_id,
            node_type="query_rewrite",
        )

    def validate_config(self, config: dict[str, Any]) -> list[str]:
        errors = []
        if "model" in config and not isinstance(config["model"], str):
            errors.append("model 必须是字符串")
        return errors
