"""混合检索节点

BM25 + 向量并行检索 → RRF 融合。
"""
from typing import Any

from src.core.pipeline.base_node import BaseNodeExecutor
from src.core.pipeline.node_context import NodeContext
from src.core.pipeline.node_result import NodeResult
from src.utils.logger import logger


class HybridSearchExecutor(BaseNodeExecutor):
    """混合检索执行器"""

    @property
    def category(self) -> str:
        return "retrieval"

    async def execute(self, context: NodeContext) -> NodeResult:
        """执行混合检索"""
        query = context.input_data
        if not query:
            return NodeResult(output=[], node_id=context.node_id, node_type="hybrid_search")

        vector_weight = context.config.get("vector_weight", 0.6)
        keyword_weight = context.config.get("keyword_weight", 0.4)
        top_k = context.config.get("top_k", 10)
        fusion_method = context.config.get("fusion_method", "rrf")
        rrf_k = context.config.get("rrf_k", 60)

        # 实际实现应：
        # 1. 并行调用 BM25 + 向量检索
        # 2. RRF 融合
        # 简化实现：返回空结果
        results = []

        logger.debug(f"混合检索: query={query}, top_k={top_k}, results={len(results)}")

        return NodeResult(
            output=results,
            metadata={
                "vector_weight": vector_weight,
                "keyword_weight": keyword_weight,
                "fusion_method": fusion_method,
            },
            node_id=context.node_id,
            node_type="hybrid_search",
        )
