"""BM25 检索节点

BM25 关键词检索，集成 BM25IndexManager。
"""
import os
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

        try:
            from src.core.knowledge_base.bm25_index import BM25IndexManager
            manager = BM25IndexManager()

            kb_id = context.knowledge_base_id or context.config.get("knowledge_base_id", "")
            tenant_id = context.auth.tenant_id

            if not kb_id:
                return NodeResult(
                    output=[], node_id=context.node_id, node_type="bm25_search",
                    metadata={"error": "knowledge_base_id 未指定"}
                )

            results = await manager.search(kb_id, tenant_id, query, top_k)

            if score_threshold > 0:
                results = [r for r in results if r.get("score", 0) >= score_threshold]

            logger.debug(f"BM25 检索: kb={kb_id}, top_k={top_k}, results={len(results)}")

            return NodeResult(
                output=results,
                metadata={"top_k": top_k, "kb_id": kb_id, "result_count": len(results)},
                node_id=context.node_id,
                node_type="bm25_search",
            )

        except Exception as e:
            logger.error(f"BM25 检索失败: {e}")
            return NodeResult(
                output=[],
                metadata={"error": str(e)},
                node_id=context.node_id,
                node_type="bm25_search",
                degraded=True,
                degradation_reason=str(e),
            )
