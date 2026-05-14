"""BM25 检索节点

BM25 关键词检索，支持 ES 后端和独立 BM25 索引。
"""
from typing import Any

from src.core.pipeline.base_node import BaseNodeExecutor
from src.core.pipeline.node_context import NodeContext
from src.core.pipeline.node_result import NodeResult
from src.utils.logger import logger


class BM25SearchExecutor(BaseNodeExecutor):
    """BM25 检索执行器"""

    @property
    def category(self) -> str:
        return "retrieval"

    async def execute(self, context: NodeContext) -> NodeResult:
        """执行 BM25 检索"""
        query = context.input_data
        if not query:
            return NodeResult(output=[], node_id=context.node_id, node_type="bm25_search")

        top_k = context.config.get("top_k", 10)
        score_threshold = context.config.get("score_threshold", 0.0)

        # 实际实现应调用 BM25IndexManager
        # 简化实现：返回空结果
        results = []

        logger.debug(f"BM25 检索: query={query}, top_k={top_k}, results={len(results)}")

        return NodeResult(
            output=results,
            metadata={"top_k": top_k, "score_threshold": score_threshold},
            node_id=context.node_id,
            node_type="bm25_search",
        )
