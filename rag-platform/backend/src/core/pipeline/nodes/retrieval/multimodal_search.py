"""多模态检索节点

文本/图片/表格多模态检索 → 融合。
"""
from typing import Any

from src.core.pipeline.base_node import BaseNodeExecutor
from src.core.pipeline.node_context import NodeContext
from src.core.pipeline.node_result import NodeResult
from src.utils.logger import logger


class MultimodalSearchExecutor(BaseNodeExecutor):
    """多模态检索执行器"""

    @property
    def category(self) -> str:
        return "retrieval"

    async def execute(self, context: NodeContext) -> NodeResult:
        """执行多模态检索"""
        query = context.input_data
        if not query:
            return NodeResult(output=[], node_id=context.node_id, node_type="multimodal_search")

        top_k = context.config.get("top_k", 10)
        weights = context.config.get("weights", {"text": 1.0, "image": 0.5, "table": 0.5})

        # 简化实现：仅使用文本检索
        # 实际实现应分别检索文本/图片/表格，然后融合
        try:
            from src.config import settings

            from src.core.knowledge_base.embedding.engine import EmbeddingEngine
            from src.core.knowledge_base.vector_store.factory import VectorStoreAdapterFactory

            embedding_config = context.config.get("embedding_config", {})
            provider = embedding_config.get("provider", "dashscope")
            api_key = (settings.llm_providers.get(provider) and settings.llm_providers[provider].api_key) or ""
            dimension = embedding_config.get("dimension", 1024)

            engine = EmbeddingEngine.from_config(provider=provider, api_key=api_key, dimension=dimension)
            query_embedding = await engine.embed_single(query)

            backend_type = context.config.get("vector_backend", "chroma")
            adapter = VectorStoreAdapterFactory.get_adapter(
                backend_type, es_url=settings.es_url or None, milvus_host=settings.milvus_host or None
            )

            kb_id = context.knowledge_base_id or context.config.get("knowledge_base_id", "")
            if not kb_id:
                return NodeResult(output=[], node_id=context.node_id, node_type="multimodal_search")

            results = await adapter.search(kb_id, context.auth.tenant_id, query_embedding, top_k)

            return NodeResult(
                output=results,
                metadata={"top_k": top_k, "modalities": list(weights.keys())},
                node_id=context.node_id,
                node_type="multimodal_search",
            )

        except Exception as e:
            logger.error(f"多模态检索失败: {e}")
            return NodeResult(
                output=[], metadata={"error": str(e)},
                node_id=context.node_id, node_type="multimodal_search",
                degraded=True, degradation_reason=str(e),
            )
