"""Elasticsearch 向量存储适配器"""
from typing import Optional

from src.core.knowledge_base.vector_store.base import CollectionInfo, VectorStoreAdapter
from src.utils.logger import logger


class ElasticsearchAdapter(VectorStoreAdapter):
    """Elasticsearch 向量存储适配器"""

    backend_type = "elasticsearch"

    def __init__(self, es_url: str = "http://localhost:9200"):
        self._es_url = es_url
        self._client = None

    async def _get_client(self):
        """获取 ES 客户端"""
        if self._client is None:
            from elasticsearch import AsyncElasticsearch
            self._client = AsyncElasticsearch(self._es_url)
        return self._client

    async def create_collection(
        self, kb_id: str, tenant_id: str, dimension: int, metadata: Optional[dict] = None
    ) -> None:
        """创建 ES Index（含 dense_vector 映射）"""
        client = await self._get_client()
        index_name = self._collection_name(kb_id, tenant_id)

        if await client.indices.exists(index=index_name):
            logger.info(f"ES Index 已存在: {index_name}")
            return

        mapping = {
            "mappings": {
                "properties": {
                    "chunk_id": {"type": "keyword"},
                    "doc_id": {"type": "keyword"},
                    "content": {"type": "text"},
                    "embedding": {
                        "type": "dense_vector",
                        "dims": dimension,
                        "index": True,
                        "similarity": "cosine",
                    },
                    "doc_acl": {"type": "keyword"},
                    "metadata": {"type": "object", "enabled": False},
                }
            }
        }
        if metadata:
            if "number_of_shards" in metadata:
                mapping["settings"] = {"number_of_shards": metadata["number_of_shards"]}

        await client.indices.create(index=index_name, body=mapping)
        logger.info(f"ES Index 创建成功: {index_name}")

    async def delete_collection(self, kb_id: str, tenant_id: str) -> None:
        """删除 ES Index"""
        client = await self._get_client()
        index_name = self._collection_name(kb_id, tenant_id)
        try:
            await client.indices.delete(index=index_name)
            logger.info(f"ES Index 删除成功: {index_name}")
        except Exception as e:
            logger.warning(f"ES Index 删除失败（可能不存在）: {index_name}, {e}")

    async def add_embeddings(
        self,
        kb_id: str,
        tenant_id: str,
        chunk_ids: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict],
        texts: list[str],
    ) -> list[str]:
        """批量添加向量到 ES"""
        client = await self._get_client()
        index_name = self._collection_name(kb_id, tenant_id)

        actions = []
        for i, chunk_id in enumerate(chunk_ids):
            doc = {
                "chunk_id": chunk_id,
                "doc_id": metadatas[i].get("doc_id", ""),
                "content": texts[i],
                "embedding": embeddings[i],
                "doc_acl": metadatas[i].get("doc_acl", []),
                "metadata": metadatas[i],
            }
            actions.append({"index": {"_index": index_name, "_id": chunk_id}})
            actions.append(doc)

        from elasticsearch.helpers import async_bulk
        await async_bulk(client, actions)
        logger.info(f"ES 添加 {len(chunk_ids)} 个向量: {index_name}")
        return chunk_ids

    async def search(
        self,
        kb_id: str,
        tenant_id: str,
        query_embedding: list[float],
        top_k: int = 10,
        filter_condition: Optional[dict] = None,
    ) -> list[dict]:
        """ES KNN 向量检索"""
        client = await self._get_client()
        index_name = self._collection_name(kb_id, tenant_id)

        query = {
            "knn": {
                "field": "embedding",
                "query_vector": query_embedding,
                "k": top_k,
                "num_candidates": top_k * 10,
            },
            "_source": ["chunk_id", "doc_id", "content", "doc_acl", "metadata"],
        }

        if filter_condition:
            query["knn"]["filter"] = filter_condition

        results = await client.search(index=index_name, body=query)

        items = []
        for hit in results.get("hits", {}).get("hits", []):
            items.append({
                "chunk_id": hit["_source"].get("chunk_id", hit["_id"]),
                "doc_id": hit["_source"].get("doc_id", ""),
                "content": hit["_source"].get("content", ""),
                "score": hit.get("_score", 0.0),
                "metadata": hit["_source"].get("metadata", {}),
            })
        return items

    async def delete_by_filter(
        self, kb_id: str, tenant_id: str, filter_condition: dict
    ) -> int:
        """按条件删除 ES 向量"""
        client = await self._get_client()
        index_name = self._collection_name(kb_id, tenant_id)

        query = {"query": {"bool": {"filter": []}}}
        for key, value in filter_condition.items():
            query["query"]["bool"]["filter"].append({"term": {key: value}})

        result = await client.delete_by_query(index=index_name, body=query)
        return result.get("deleted", 0)

    async def get_collection_info(self, kb_id: str, tenant_id: str) -> CollectionInfo:
        """获取 ES Index 信息"""
        client = await self._get_client()
        index_name = self._collection_name(kb_id, tenant_id)

        try:
            stats = await client.indices.stats(index=index_name)
            doc_count = stats["_all"]["primaries"]["docs"]["count"]
            size_bytes = stats["_all"]["primaries"]["store"]["size_in_bytes"]
        except Exception:
            doc_count = 0
            size_bytes = 0

        return CollectionInfo(
            name=index_name,
            vector_count=doc_count,
            storage_size_bytes=size_bytes,
        )
