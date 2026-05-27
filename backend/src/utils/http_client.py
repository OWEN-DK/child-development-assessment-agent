"""RAG API 异步 HTTP 客户端

供 search_knowledge_base 工具调用 RAG 检索 API。
每个请求创建独立的客户端实例，通过 ContextVar 传递，避免并发请求间的干扰。
"""

import os
from typing import Any, Dict, List, Optional

import httpx

from src.utils.logger import logger


class RagHttpClient:
    """RAG API HTTP 客户端（请求级实例，由 Service 管理生命周期）"""

    def __init__(self, base_url: str = ""):
        if not base_url:
            base_url = os.getenv("API_BASE_URL", "")
        if not base_url:
            # 从应用配置自动推导（避免硬编码端口）
            try:
                from src.config import settings
                host = getattr(settings, "app_host", "127.0.0.1")
                port = getattr(settings, "app_port", 8000)
                base_url = f"http://{host}:{port}"
            except Exception:
                base_url = "http://127.0.0.1:8000"
        self._base_url = base_url
        self._client: Optional[httpx.AsyncClient] = None

    async def _ensure_client(self):
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                timeout=httpx.Timeout(10.0),
                limits=httpx.Limits(
                    max_connections=10,
                    max_keepalive_connections=5,
                ),
            )

    async def search_chunks(
        self,
        question: str,
        book_ids: Optional[List[str]] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """检索知识库分块

        Args:
            question: 检索查询词
            book_ids: 可选，限制在指定书籍 ID 内检索
            limit: 返回结果数

        Returns:
            检索结果列表，每项含 chunk_id, text, chapter, section, page,
            book_title, source_document_id, score 等字段
        """
        await self._ensure_client()
        params: Dict[str, Any] = {
            "query": question,
            "limit": str(limit),
        }
        if book_ids:
            params["book_ids"] = ",".join(book_ids)

        resp = await self._client.get("/rag/search", params=params)
        resp.raise_for_status()
        data = resp.json()
        return data.get("data", {}).get("results", [])

    async def get_graph_node(self, node_id: str) -> dict | None:
        """获取单个社区节点（HTTP 调用 RAG 服务）"""
        await self._ensure_client()
        try:
            resp = await self._client.get(f"/rag/graph/nodes/{node_id}")
            resp.raise_for_status()
            data = resp.json()
            node = data.get("data", {}).get("node")
            return node
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise

    async def get_graph_children_batch(self, parent_ids: list[str]) -> dict[str, list[dict]]:
        """批量查询多个父节点的子节点（HTTP 调用 RAG 服务，单次请求）"""
        await self._ensure_client()
        resp = await self._client.get(
            "/rag/graph/children-batch",
            params={"parent_ids": ",".join(parent_ids)},
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("data", {}).get("children_map", {})


    async def get_graph_roots(
        self,
        scope: str = "book",
        book_id: str | None = None,
    ) -> list[dict]:
        """获取社区树根节点列表（HTTP 调用 RAG 服务）"""
        await self._ensure_client()
        params: dict[str, str] = {"scope": scope}
        if book_id:
            params["book_id"] = book_id
        resp = await self._client.get("/rag/graph/roots", params=params)
        resp.raise_for_status()
        data = resp.json()
        return data.get("data", {}).get("roots", [])

    async def get_graph_children(self, node_id: str) -> list[dict]:
        """获取社区节点的直接子节点（HTTP 调用 RAG 服务）"""
        await self._ensure_client()
        resp = await self._client.get(f"/rag/graph/children/{node_id}")
        resp.raise_for_status()
        data = resp.json()
        return data.get("data", {}).get("children", [])


    async def batch_resolve_books(
        self,
        ids: list[str],
    ) -> list[dict]:
        """批量解析书籍标识符 → [{id, file_name, file_hash}]

        通过 HTTP 调用 RAG 服务，不直接访问数据库。
        """
        await self._ensure_client()
        resp = await self._client.get(
            "/rag/books/batch-resolve",
            params={"ids": ",".join(ids)},
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("data", {}).get("books", [])

    async def filter_graph_ready(
        self,
        book_ids: list[str],
    ) -> list[str]:
        """过滤出 graph_ready=True 的书籍 UUID 列表

        通过 HTTP 调用 RAG 服务，不直接访问数据库。
        """
        if not book_ids:
            return []
        await self._ensure_client()
        resp = await self._client.get(
            "/rag/books/graph-ready",
            params={"book_ids": ",".join(book_ids)},
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("data", {}).get("ready_ids", [])


    async def upsert_entities(self, book_id: str, entities: list[dict]) -> int:
        """批量 upsert 图谱实体（HTTP POST 调用 RAG 服务）"""
        await self._ensure_client()
        resp = await self._client.post(
            "/rag/graph/entities/upsert",
            params={"book_id": book_id},
            json=entities,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("data", {}).get("count", 0)

    async def insert_relations(self, book_id: str, relations: list[dict]) -> int:
        """批量插入图谱关系（HTTP POST 调用 RAG 服务，服务端解析实体名→ID）"""
        await self._ensure_client()
        resp = await self._client.post(
            "/rag/graph/relations/insert",
            params={"book_id": book_id},
            json=relations,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("data", {}).get("count", 0)

    async def store_communities(
        self,
        tree_nodes: list[dict],
        tree_edges: list[dict] | None = None,
        book_id: str | None = None,
        scope: str = "book",
    ) -> int:
        """存储层级社区树（HTTP POST 调用 RAG 服务）"""
        await self._ensure_client()
        params: dict[str, str] = {"scope": scope}
        if book_id:
            params["book_id"] = book_id
        resp = await self._client.post(
            "/rag/graph/communities/store",
            params=params,
            json={
                "tree_nodes": tree_nodes,
                "tree_edges": tree_edges or [],
            },
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("data", {}).get("count", 0)

    async def delete_entities_by_book(self, book_id: str) -> int:
        """删除指定书籍的所有图谱实体（HTTP DELETE）"""
        await self._ensure_client()
        resp = await self._client.delete(f"/rag/graph/entities/book/{book_id}")
        resp.raise_for_status()
        data = resp.json()
        return data.get("data", {}).get("count", 0)

    async def delete_relations_by_book(self, book_id: str) -> int:
        """删除指定书籍的所有图谱关系（HTTP DELETE）"""
        await self._ensure_client()
        resp = await self._client.delete(f"/rag/graph/relations/book/{book_id}")
        resp.raise_for_status()
        data = resp.json()
        return data.get("data", {}).get("count", 0)

    async def delete_communities_by_book(self, book_id: str) -> int:
        """删除指定书籍的所有社区节点（HTTP DELETE）"""
        await self._ensure_client()
        resp = await self._client.delete(f"/rag/graph/communities/book/{book_id}")
        resp.raise_for_status()
        data = resp.json()
        return data.get("data", {}).get("count", 0)

    async def delete_communities_by_scope(self, scope: str) -> int:
        """删除指定作用域的所有社区节点（HTTP DELETE）"""
        await self._ensure_client()
        resp = await self._client.delete(f"/rag/graph/communities/scope/{scope}")
        resp.raise_for_status()
        data = resp.json()
        return data.get("data", {}).get("count", 0)



class HttpGraphAdapter:
    """通过 HTTP 调用 RAG 服务的社区树查询适配器。

    提供与 GraphCommunityRepository 相同的方法签名，
    但所有数据访问通过 HTTP API 而非直接数据库查询。
    用于 knowledge-qa 模块，为后续知识库独立部署做准备。
    """

    def __init__(self, client: "RagHttpClient"):
        self._client = client

    async def get_node(self, node_id: str) -> dict | None:
        """获取社区节点。返回 dict 或 None。"""
        return await self._client.get_graph_node(node_id)

    async def get_children(self, parent_id: str) -> list[dict]:
        """获取直接子节点列表。"""
        return await self._client.get_graph_children(parent_id)

    async def get_children_batch(self, parent_ids: list[str]) -> dict[str, list[dict]]:
        """批量获取子节点。返回 {parent_id: [children]}。"""
        return await self._client.get_graph_children_batch(parent_ids)

    async def store_communities(
        self,
        tree_nodes: list[dict],
        tree_edges: list[dict] | None = None,
        book_id: str | None = None,
        scope: str = "book",
    ) -> int:
        """存储层级社区树（委托 HTTP 客户端）。"""
        return await self._client.store_communities(
            tree_nodes=tree_nodes,
            tree_edges=tree_edges,
            book_id=book_id,
            scope=scope,
        )

    async def delete_by_book(self, book_id: str) -> int:
        """删除指定书籍的所有社区节点（委托 HTTP 客户端）。"""
        return await self._client.delete_communities_by_book(book_id)

    async def delete_by_scope(self, scope: str) -> int:
        """删除指定作用域的所有社区节点（委托 HTTP 客户端）。"""
        return await self._client.delete_communities_by_scope(scope)


    async def get_roots(self, scope: str = "book", book_id: str | None = None) -> list[dict]:
        """获取根节点列表。"""
        return await self._client.get_graph_roots(scope=scope, book_id=book_id)

    async def close(self):
        """关闭 HTTP 客户端，释放连接池"""
        if self._client:
            await self._client.aclose()
            self._client = None
