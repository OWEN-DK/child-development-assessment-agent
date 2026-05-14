"""向量检索节点

向量相似度检索，支持 ACL 过滤。
"""
from typing import Any

from src.core.pipeline.base_node import BaseNodeExecutor
from src.core.pipeline.node_context import NodeContext
from src.core.pipeline.node_result import NodeResult
from src.utils.logger import logger


class VectorSearchExecutor(BaseNodeExecutor):
    """向量检索执行器"""

    @property
    def category(self) -> str:
        return "retrieval"

    async def execute(self, context: NodeContext) -> NodeResult:
        """执行向量检索"""
        query = context.input_data
        if not query:
            return NodeResult(output=[], node_id=context.node_id, node_type="vector_search")

        top_k = context.config.get("top_k", 10)
        similarity_threshold = context.config.get("similarity_threshold", 0.0)

        # 实际实现应：
        # 1. 调用 EmbeddingEngine 获取查询向量
        # 2. 构建 ACL 过滤条件
        # 3. 调用 VectorStoreAdapter.search()
        # 简化实现：返回空结果
        results = []

        logger.debug(f"向量检索: query={query}, top_k={top_k}, results={len(results)}")

        return NodeResult(
            output=results,
            metadata={"top_k": top_k, "similarity_threshold": similarity_threshold},
            node_id=context.node_id,
            node_type="vector_search",
        )
