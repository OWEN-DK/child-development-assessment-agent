"""向量存储适配器抽象基类

定义三种向量后端（Chroma/Elasticsearch/Milvus）的统一接口。
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class CollectionInfo:
    """Collection 统计信息"""
    name: str
    vector_count: int = 0
    dimension: int = 0
    storage_size_bytes: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


class VectorStoreAdapter(ABC):
    """向量存储适配器抽象基类"""

    backend_type: str  # "chroma" | "elasticsearch" | "milvus"

    @abstractmethod
    async def create_collection(
        self, kb_id: str, tenant_id: str, dimension: int, metadata: Optional[dict] = None
    ) -> None:
        """创建知识库对应的 Collection/Index

        Args:
            kb_id: 知识库 ID
            tenant_id: 租户 ID
            dimension: 向量维度
            metadata: 后端特定配置（如 Chroma hnsw:space, ES shards）
        """

    @abstractmethod
    async def delete_collection(self, kb_id: str, tenant_id: str) -> None:
        """删除 Collection/Index"""

    @abstractmethod
    async def add_embeddings(
        self,
        kb_id: str,
        tenant_id: str,
        chunk_ids: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict],
        texts: list[str],
    ) -> list[str]:
        """批量添加向量

        Args:
            kb_id: 知识库 ID
            tenant_id: 租户 ID
            chunk_ids: 分块 ID 列表
            embeddings: 向量列表
            metadatas: 元数据列表
            texts: 文本内容列表（ES 需要存储文本用于全文搜索）

        Returns:
            后端分配的 vector_id 列表
        """

    @abstractmethod
    async def search(
        self,
        kb_id: str,
        tenant_id: str,
        query_embedding: list[float],
        top_k: int = 10,
        filter_condition: Optional[dict] = None,
    ) -> list[dict]:
        """向量检索

        Args:
            kb_id: 知识库 ID
            tenant_id: 租户 ID
            query_embedding: 查询向量
            top_k: 返回数量
            filter_condition: ACL 过滤条件

        Returns:
            [{chunk_id, doc_id, content, score, metadata}, ...]
        """

    @abstractmethod
    async def delete_by_filter(
        self, kb_id: str, tenant_id: str, filter_condition: dict
    ) -> int:
        """按条件删除向量

        Args:
            filter_condition: 过滤条件（如 {"doc_id": "doc_001"}）

        Returns:
            删除数量
        """

    @abstractmethod
    async def get_collection_info(self, kb_id: str, tenant_id: str) -> CollectionInfo:
        """获取 Collection 统计信息"""

    def _collection_name(self, kb_id: str, tenant_id: str) -> str:
        """命名约定：Chroma 用 {tenant_id}_{kb_id}，ES/Milvus 用 rag_{tenant_id}_{kb_id}"""
        if self.backend_type == "chroma":
            return f"{tenant_id}_{kb_id}"
        return f"rag_{tenant_id}_{kb_id}".lower()
