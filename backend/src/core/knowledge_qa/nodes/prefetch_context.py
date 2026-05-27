"""知识上下文预取节点

在 match_books 之后、内容节之前运行。
利用 match_books 产出的 matched_book_ids 执行 LazyGraphRAG 社区树遍历，
将知识上下文注入到 State 中，供后续节点的 Agent 使用。

此节点不调用 LLM，仅做数据检索和组装。独立 30s 超时，失败退化为纯 Agent 模式。
"""

import asyncio
import logging
from typing import Any, Dict

from src.schemas.knowledge_qa import KnowledgeQAState, push_progress

logger = logging.getLogger(__name__)

PREFETCH_TIMEOUT_SECONDS = 10


async def prefetch_context_node(state: KnowledgeQAState) -> Dict[str, Any]:
    """知识上下文预取：match_books → LazyGraphRAG 遍历 → knowledge_context"""
    await push_progress("prefetch_context", "正在预取知识上下文…")

    if state.knowledge_context:
        return {"current_step": ["prefetch_context_skipped"]}

    book_ids = state.matched_book_ids
    if not book_ids:
        return {"current_step": ["prefetch_context_no_books"]}

    try:
        result = await asyncio.wait_for(
            _do_prefetch(state.question, book_ids),
            timeout=PREFETCH_TIMEOUT_SECONDS,
        )
        if result:
            return result

    except asyncio.TimeoutError:
        logger.warning(
            f"知识上下文预取超时 ({PREFETCH_TIMEOUT_SECONDS}s)，退化为纯 Agent 模式"
        )
    except Exception as e:
        logger.warning(f"知识上下文预取失败: {e}，退化为纯 Agent 模式")

    # 超时或失败：清空 knowledge_context 确保无残留截断数据
    return {"knowledge_context": "", "current_step": ["prefetch_context_empty"]}


async def _do_prefetch(question: str, book_ids: list[str]) -> Dict[str, Any] | None:
    """执行实际的社区树遍历和知识上下文构建。

    所有图谱数据访问通过 HTTP 调用 RAG 服务（不直接访问数据库），
    为后续知识库独立部署做准备。
    """
    from src.core.knowledge_qa.graph.traversal import (
        TraversalHit,
        build_knowledge_context,
        explore_community_tree,
    )
    from src.core.knowledge_qa.tools import _get_http_client
    from src.utils.http_client import HttpGraphAdapter

    community_repo = HttpGraphAdapter(_get_http_client())

    ready_ids = await _filter_graph_ready(book_ids)
    if not ready_ids:
        return {"current_step": ["prefetch_context_no_graph_ready"]}

    all_hits: list[TraversalHit] = []

    for book_id in ready_ids:
        roots = await community_repo.get_roots(scope="book", book_id=book_id)
        for root in roots:
            hits = await explore_community_tree(
                question=question,
                root_id=root.node_id,
                community_repo=community_repo,
            )
            all_hits.extend(hits)

    global_roots = await community_repo.get_roots(scope="global")
    for root in global_roots:
        hits = await explore_community_tree(
            question=question,
            root_id=root.node_id,
            community_repo=community_repo,
        )
        all_hits.extend(hits)

    if all_hits:
        seen_chunks: set[str] = set()
        deduped: list[TraversalHit] = []
        for hit in all_hits:
            unique = [c for c in hit.chunk_ids if c not in seen_chunks]
            seen_chunks.update(unique)
            if unique:
                deduped.append(TraversalHit(
                    node_id=hit.node_id,
                    label=hit.label,
                    entity_names=hit.entity_names,
                    chunk_ids=unique,
                ))

        if deduped:
            context = await build_knowledge_context(
                question=question,
                hits=deduped,
                chunk_loader=_make_chunk_loader(),
            )
            if context:
                logger.info(f"知识上下文预取完成: {len(context)} 字符, {len(deduped)} 社区")
                return {
                    "knowledge_context": context,
                    "current_step": ["prefetch_context_done"],
                }

    return None


async def _filter_graph_ready(book_ids: list[str]) -> list[str]:
    """通过 HTTP 调用 RAG 服务过滤出 graph_ready=True 的书籍 UUID 列表。

    先前直接查询知识库数据库，现已改为 HTTP 调用 /rag/books/graph-ready，
    为后续知识库独立部署做准备。
    """
    if not book_ids:
        return []

    try:
        from src.core.knowledge_qa.tools import _get_http_client

        client = _get_http_client()
        return await client.filter_graph_ready(book_ids)
    except Exception as e:
        logger.warning(f"批量 graph_ready 查询失败 (HTTP): {e}")
        return []


def _make_chunk_loader():
    """创建块文本加载器（从 LlamaIndex docstore 加载）。"""
    async def load_chunks(chunk_ids: list[str]) -> dict[str, str]:
        from src.service.index_manager_service import index_manager_service

        result: dict[str, str] = {}
        if not index_manager_service.is_index_available():
            return result

        index = index_manager_service.get_index()
        if not hasattr(index, "docstore"):
            return result

        for cid in chunk_ids:
            node = index.docstore.docs.get(cid)
            if node and hasattr(node, "get_content"):
                result[cid] = node.get_content()
        return result

    return load_chunks
