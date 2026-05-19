"""混合检索节点

BM25 + 向量并行检索 → RRF 融合。
"""
import asyncio
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
        """执行混合检索（BM25 + 向量并行 → RRF 融合）"""
        query = context.input_data
        if not query:
            return NodeResult(output=[], node_id=context.node_id, node_type="hybrid_search")

        top_k = context.config.get("top_k", 10)
        vector_weight = context.config.get("vector_weight", 0.6)
        keyword_weight = context.config.get("keyword_weight", 0.4)
        rrf_k = context.config.get("rrf_k", 60)

        kb_id = context.knowledge_base_id or context.config.get("knowledge_base_id", "")
        tenant_id = context.auth.tenant_id

        if not kb_id:
            return NodeResult(
                output=[], node_id=context.node_id, node_type="hybrid_search",
                metadata={"error": "knowledge_base_id 未指定"}
            )

        try:
            # 并行执行 BM25 + 向量检索
            bm25_task = self._bm25_search(query, kb_id, tenant_id, top_k)
            vector_task = self._vector_search(query, kb_id, tenant_id, top_k, context)

            bm25_results, vector_results = await asyncio.gather(
                bm25_task, vector_task, return_exceptions=True
            )

            if isinstance(bm25_results, Exception):
                logger.warning(f"BM25 检索失败: {bm25_results}")
                bm25_results = []
            if isinstance(vector_results, Exception):
                logger.warning(f"向量检索失败: {vector_results}")
                vector_results = []

            # RRF 融合
            fused = self._rrf_fusion(bm25_results, vector_results, rrf_k, keyword_weight, vector_weight)

            logger.debug(f"混合检索: kb={kb_id}, bm25={len(bm25_results)}, vector={len(vector_results)}, fused={len(fused)}")

            return NodeResult(
                output=fused[:top_k],
                metadata={
                    "bm25_count": len(bm25_results),
                    "vector_count": len(vector_results),
                    "fusion_method": "rrf",
                },
                node_id=context.node_id,
                node_type="hybrid_search",
            )

        except Exception as e:
            logger.error(f"混合检索失败: {e}")
            return NodeResult(
                output=[],
                metadata={"error": str(e)},
                node_id=context.node_id,
                node_type="hybrid_search",
                degraded=True,
                degradation_reason=str(e),
            )

    async def _bm25_search(self, query: str, kb_id: str, tenant_id: str, top_k: int) -> list[dict]:
        from src.core.knowledge_base.bm25_index import BM25IndexManager
        manager = BM25IndexManager()
        return await manager.search(kb_id, tenant_id, query, top_k)

    async def _vector_search(self, query: str, kb_id: str, tenant_id: str, top_k: int, context: NodeContext) -> list[dict]:
        from src.core.knowledge_base.embedding.engine import EmbeddingEngine
        from src.core.knowledge_base.vector_store.factory import VectorStoreAdapterFactory
        from src.core.knowledge_base.acl_filter import get_acl_filter_builder

        from src.config import settings

        embedding_config = context.config.get("embedding_config", {})
        provider = embedding_config.get("provider", "dashscope")
        api_key = (settings.llm_providers.get(provider) and settings.llm_providers[provider].api_key) or ""
        dimension = embedding_config.get("dimension", 1024)

        engine = EmbeddingEngine.from_config(provider=provider, api_key=api_key, dimension=dimension)
        query_embedding = await engine.embed_single(query)

        backend_type = context.config.get("vector_backend", "chroma")
        builder = get_acl_filter_builder(backend_type)
        filter_condition = builder.build_filter(context.auth.roles)

        adapter = VectorStoreAdapterFactory.get_adapter(
            backend_type, es_url=settings.es_url or None, milvus_host=settings.milvus_host or None
        )
        return await adapter.search(kb_id, tenant_id, query_embedding, top_k, filter_condition or None)

    def _rrf_fusion(
        self, bm25_results: list[dict], vector_results: list[dict],
        rrf_k: int, bm25_weight: float, vector_weight: float
    ) -> list[dict]:
        """RRF (Reciprocal Rank Fusion) 融合"""
        scores: dict[str, float] = {}
        chunk_data: dict[str, dict] = {}

        for rank, item in enumerate(bm25_results):
            chunk_id = item.get("chunk_id", "")
            scores[chunk_id] = scores.get(chunk_id, 0) + bm25_weight / (rrf_k + rank + 1)
            chunk_data[chunk_id] = item

        for rank, item in enumerate(vector_results):
            chunk_id = item.get("chunk_id", "")
            scores[chunk_id] = scores.get(chunk_id, 0) + vector_weight / (rrf_k + rank + 1)
            chunk_data[chunk_id] = item

        sorted_ids = sorted(scores.keys(), key=lambda cid: scores[cid], reverse=True)

        results = []
        for chunk_id in sorted_ids:
            item = chunk_data[chunk_id].copy()
            item["rrf_score"] = scores[chunk_id]
            results.append(item)

        return results
