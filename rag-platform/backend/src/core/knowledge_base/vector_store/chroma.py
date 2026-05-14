"""Chroma 向量存储适配器

使用 asyncio.to_thread() 包装同步 Chroma 调用，避免阻塞事件循环。
"""
import asyncio
from typing import Optional

from src.core.knowledge_base.vector_store.base import CollectionInfo, VectorStoreAdapter
from src.utils.logger import logger


class ChromaAdapter(VectorStoreAdapter):
    """Chroma 向量存储适配器"""

    backend_type = "chroma"

    def __init__(self, storage_dir: str = "./app_data/storage/chroma"):
        self._storage_dir = storage_dir
        self._clients: dict[str, object] = {}

    def _get_client(self, collection_name: str):
        """获取或创建 Chroma client（同步）"""
        import chromadb

        if collection_name not in self._clients:
            path = f"{self._storage_dir}/{collection_name}"
            client = chromadb.PersistentClient(path=path)
            self._clients[collection_name] = client
        return self._clients[collection_name]

    async def create_collection(
        self, kb_id: str, tenant_id: str, dimension: int, metadata: Optional[dict] = None
    ) -> None:
        """创建 Chroma Collection，强制 hnsw:space=cosine"""
        name = self._collection_name(kb_id, tenant_id)

        def _create():
            client = self._get_client(name)
            collection_metadata = {"hnsw:space": "cosine"}
            if metadata:
                collection_metadata.update(metadata)
            client.get_or_create_collection(name=name, metadata=collection_metadata)

        await asyncio.to_thread(_create)
        logger.info(f"Chroma Collection 创建成功: {name}")

    async def delete_collection(self, kb_id: str, tenant_id: str) -> None:
        """删除 Chroma Collection"""
        name = self._collection_name(kb_id, tenant_id)

        def _delete():
            client = self._get_client(name)
            try:
                client.delete_collection(name)
            except Exception as e:
                logger.warning(f"Chroma Collection 删除失败（可能不存在）: {name}, {e}")

        await asyncio.to_thread(_delete)
        logger.info(f"Chroma Collection 删除操作完成: {name}")

    async def add_embeddings(
        self,
        kb_id: str,
        tenant_id: str,
        chunk_ids: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict],
        texts: list[str],
    ) -> list[str]:
        """批量添加向量到 Chroma"""
        name = self._collection_name(kb_id, tenant_id)

        def _add():
            client = self._get_client(name)
            collection = client.get_collection(name)
            collection.add(
                ids=chunk_ids,
                embeddings=embeddings,
                metadatas=metadatas,
                documents=texts,
            )

        await asyncio.to_thread(_add)
        logger.info(f"Chroma 添加 {len(chunk_ids)} 个向量: {name}")
        return chunk_ids

    async def search(
        self,
        kb_id: str,
        tenant_id: str,
        query_embedding: list[float],
        top_k: int = 10,
        filter_condition: Optional[dict] = None,
    ) -> list[dict]:
        """Chroma 向量检索"""
        name = self._collection_name(kb_id, tenant_id)

        def _search():
            client = self._get_client(name)
            collection = client.get_collection(name)

            kwargs = {
                "query_embeddings": [query_embedding],
                "n_results": top_k,
            }
            if filter_condition:
                kwargs["where"] = filter_condition

            return collection.query(**kwargs)

        results = await asyncio.to_thread(_search)

        items = []
        if results and results["ids"] and results["ids"][0]:
            for i, chunk_id in enumerate(results["ids"][0]):
                items.append({
                    "chunk_id": chunk_id,
                    "doc_id": results["metadatas"][0][i].get("doc_id", ""),
                    "content": results["documents"][0][i] if results["documents"] else "",
                    "score": 1.0 - results["distances"][0][i] if results["distances"] else 0.0,
                    "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                })
        return items

    async def delete_by_filter(
        self, kb_id: str, tenant_id: str, filter_condition: dict
    ) -> int:
        """按条件删除 Chroma 向量"""
        name = self._collection_name(kb_id, tenant_id)

        def _delete():
            client = self._get_client(name)
            collection = client.get_collection(name)
            results = collection.get(where=filter_condition)
            if results and results["ids"]:
                collection.delete(ids=results["ids"])
                return len(results["ids"])
            return 0

        return await asyncio.to_thread(_delete)

    async def get_collection_info(self, kb_id: str, tenant_id: str) -> CollectionInfo:
        """获取 Chroma Collection 信息"""
        name = self._collection_name(kb_id, tenant_id)

        def _info():
            client = self._get_client(name)
            collection = client.get_collection(name)
            return CollectionInfo(
                name=name,
                vector_count=collection.count(),
                metadata=collection.metadata or {},
            )

        return await asyncio.to_thread(_info)
