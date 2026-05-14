"""Milvus 向量存储适配器"""
from typing import Optional

from src.core.knowledge_base.vector_store.base import CollectionInfo, VectorStoreAdapter
from src.utils.logger import logger


class MilvusAdapter(VectorStoreAdapter):
    """Milvus 向量存储适配器"""

    backend_type = "milvus"

    def __init__(self, host: str = "localhost", port: int = 19530):
        self._host = host
        self._port = port
        self._connected = False

    def _ensure_connected(self):
        """确保 Milvus 连接"""
        if not self._connected:
            from pymilvus import connections
            connections.connect(host=self._host, port=self._port)
            self._connected = True

    async def create_collection(
        self, kb_id: str, tenant_id: str, dimension: int, metadata: Optional[dict] = None
    ) -> None:
        """创建 Milvus Collection"""
        self._ensure_connected()
        from pymilvus import CollectionSchema, DataType, FieldSchema, Collection

        collection_name = self._collection_name(kb_id, tenant_id)

        fields = [
            FieldSchema(name="chunk_id", dtype=DataType.VARCHAR, is_primary=True, max_length=64),
            FieldSchema(name="doc_id", dtype=DataType.VARCHAR, max_length=64),
            FieldSchema(name="content", dtype=DataType.VARCHAR, max_length=65535),
            FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=dimension),
            FieldSchema(name="doc_acl", dtype=DataType.VARCHAR, max_length=65535),  # JSON 字符串
        ]

        schema = CollectionSchema(fields=fields, enable_dynamic_field=True)
        collection = Collection(name=collection_name, schema=schema)

        # 创建 HNSW 索引
        index_params = {
            "metric_type": "COSINE",
            "index_type": "HNSW",
            "params": {"M": 16, "efConstruction": 256},
        }
        collection.create_index(field_name="embedding", index_params=index_params)
        logger.info(f"Milvus Collection 创建成功: {collection_name}")

    async def delete_collection(self, kb_id: str, tenant_id: str) -> None:
        """删除 Milvus Collection"""
        self._ensure_connected()
        from pymilvus import Collection

        collection_name = self._collection_name(kb_id, tenant_id)
        try:
            Collection(name=collection_name).drop()
            logger.info(f"Milvus Collection 删除成功: {collection_name}")
        except Exception as e:
            logger.warning(f"Milvus Collection 删除失败: {collection_name}, {e}")

    async def add_embeddings(
        self,
        kb_id: str,
        tenant_id: str,
        chunk_ids: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict],
        texts: list[str],
    ) -> list[str]:
        """批量添加向量到 Milvus"""
        self._ensure_connected()
        from pymilvus import Collection
        import json

        collection_name = self._collection_name(kb_id, tenant_id)
        collection = Collection(name=collection_name)

        data = [
            chunk_ids,
            [m.get("doc_id", "") for m in metadatas],
            texts,
            embeddings,
            [json.dumps(m.get("doc_acl", [])) for m in metadatas],
        ]

        collection.insert(data)
        collection.flush()
        logger.info(f"Milvus 添加 {len(chunk_ids)} 个向量: {collection_name}")
        return chunk_ids

    async def search(
        self,
        kb_id: str,
        tenant_id: str,
        query_embedding: list[float],
        top_k: int = 10,
        filter_condition: Optional[dict] = None,
    ) -> list[dict]:
        """Milvus 向量检索"""
        self._ensure_connected()
        from pymilvus import Collection
        import json

        collection_name = self._collection_name(kb_id, tenant_id)
        collection = Collection(name=collection_name)
        collection.load()

        search_params = {"metric_type": "COSINE", "params": {"ef": 128}}

        kwargs = {
            "data": [query_embedding],
            "anns_field": "embedding",
            "param": search_params,
            "limit": top_k,
            "output_fields": ["chunk_id", "doc_id", "content", "doc_acl"],
        }
        if filter_condition:
            kwargs["expr"] = filter_condition.get("expr", "")

        results = collection.search(**kwargs)

        items = []
        for hits in results:
            for hit in hits:
                doc_acl_raw = hit.entity.get("doc_acl", "[]")
                try:
                    doc_acl = json.loads(doc_acl_raw) if isinstance(doc_acl_raw, str) else doc_acl_raw
                except (json.JSONDecodeError, TypeError):
                    doc_acl = []

                items.append({
                    "chunk_id": hit.entity.get("chunk_id", hit.id),
                    "doc_id": hit.entity.get("doc_id", ""),
                    "content": hit.entity.get("content", ""),
                    "score": hit.score,
                    "metadata": {"doc_acl": doc_acl},
                })
        return items

    async def delete_by_filter(
        self, kb_id: str, tenant_id: str, filter_condition: dict
    ) -> int:
        """按条件删除 Milvus 向量"""
        self._ensure_connected()
        from pymilvus import Collection

        collection_name = self._collection_name(kb_id, tenant_id)
        collection = Collection(name=collection_name)

        expr = filter_condition.get("expr", "")
        if not expr:
            return 0

        result = collection.delete(expr)
        return len(result.primary_keys) if result else 0

    async def get_collection_info(self, kb_id: str, tenant_id: str) -> CollectionInfo:
        """获取 Milvus Collection 信息"""
        self._ensure_connected()
        from pymilvus import Collection

        collection_name = self._collection_name(kb_id, tenant_id)
        try:
            collection = Collection(name=collection_name)
            collection.flush()
            return CollectionInfo(
                name=collection_name,
                vector_count=collection.num_entities,
            )
        except Exception:
            return CollectionInfo(name=collection_name)
