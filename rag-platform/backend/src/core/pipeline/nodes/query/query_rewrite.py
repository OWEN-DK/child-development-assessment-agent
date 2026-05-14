"""查询改写节点

LLM 调用改写查询，输出查询变体列表。
"""
import json
from typing import Any

from src.core.pipeline.base_node import BaseNodeExecutor
from src.core.pipeline.llm_helper import call_llm_json
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
        max_retries = context.config.get("max_retries", 2)

        system_prompt = """你是一个查询改写专家。将用户查询改写为更适合检索的形式。
要求：
1. 保持语义不变
2. 使查询更精确、更适合向量检索
3. 返回 JSON 数组，包含 2-3 个改写变体

示例输出：["改写变体1", "改写变体2", "改写变体3"]"""

        prompt = f"请改写以下查询：\n{query}"

        try:
            result = await call_llm_json(
                prompt=prompt,
                model=model,
                temperature=0.7,
                system_prompt=system_prompt,
            )

            if isinstance(result, list) and all(isinstance(v, str) for v in result):
                variants = result
            else:
                variants = [query]
                logger.warning(f"查询改写返回格式异常，使用原查询")

        except Exception as e:
            logger.warning(f"查询改写失败，使用原查询: {e}")
            variants = [query]

        logger.debug(f"查询改写: {query} → {len(variants)} 个变体")

        return NodeResult(
            output=variants,
            metadata={"original_query": query, "model": model, "variant_count": len(variants)},
            node_id=context.node_id,
            node_type="query_rewrite",
        )

    def validate_config(self, config: dict[str, Any]) -> list[str]:
        errors = []
        if "model" in config and not isinstance(config["model"], str):
            errors.append("model 必须是字符串")
        return errors
