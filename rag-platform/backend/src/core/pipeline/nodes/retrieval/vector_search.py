"""向量检索节点

向量相似度检索，支持 ACL 过滤。
集成 EmbeddingEngine + VectorStoreAdapter。
"""
import os
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

        try:
            # 1. 获取查询向量
            from src.core.knowledge_base.embedding.engine import EmbeddingEngine
            embedding_config = context.config.get("embedding_config", {})
            provider = embedding_config.get("provider", "dashscope")
            api_key = os.getenv(f"{provider.upper()}_API_KEY", "")
            dimension = embedding_config.get("dimension", 1024)

            engine = EmbeddingEngine.from_config(
                provider=provider, api_key=api_key, dimension=dimension
            )
            query_embedding = await engine.embed_single(query)

            # 2. 构建 ACL 过滤条件
            from src.core.knowledge_base.acl_filter import get_acl_filter_builder
            backend_type = context.config.get("vector_backend", "chroma")
            builder = get_acl_filter_builder(backend_type)
            filter_condition = builder.build_filter(context.auth.roles)

            # 3. 调用向量检索
            from src.core.knowledge_base.vector_store.factory import VectorStoreAdapterFactory
            adapter = VectorStoreAdapterFactory.get_adapter(
                backend_type,
                es_url=os.getenv("ES_URL"),
                milvus_host=os.getenv("MILVUS_HOST"),
            )

            kb_id = context.knowledge_base_id or context.config.get("knowledge_base_id", "")
            tenant_id = context.auth.tenant_id

            if not kb_id:
                return NodeResult(
                    output=[], node_id=context.node_id, node_type="vector_search",
                    metadata={"error": "knowledge_base_id 未指定"}
                )

            results = await adapter.search(
                kb_id=kb_id,
                tenant_id=tenant_id,
                query_embedding=query_embedding,
                top_k=top_k,
                filter_condition=filter_condition if filter_condition else None,
            )

            # 过滤低分结果
            if similarity_threshold > 0:
                results = [r for r in results if r.get("score", 0) >= similarity_threshold]

            logger.debug(f"向量检索: kb={kb_id}, top_k={top_k}, results={len(results)}")

            return NodeResult(
                output=results,
                metadata={"top_k": top_k, "kb_id": kb_id, "result_count": len(results)},
                node_id=context.node_id,
                node_type="vector_search",
            )

        except Exception as e:
            logger.error(f"向量检索失败: {e}")
            return NodeResult(
                output=[],
                metadata={"error": str(e)},
                node_id=context.node_id,
                node_type="vector_search",
                degraded=True,
                degradation_reason=str(e),
            )
