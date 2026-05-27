"""LazyGraphRAG 导入流水线编排

完整流程：实体提取 → 图构建 → 社区检测 → 层级树存储 → 实体/关系持久化
每本书导入完成后调用一次。
"""

import asyncio
import logging
from typing import Any

from src.core.knowledge_qa.graph.builder import (
    assign_chunks_to_communities,
    build_graph,
    dendrogram_to_tree,
    store_community_tree,
)
from src.core.knowledge_qa.graph.community import detect_communities
from src.core.knowledge_qa.graph.extractor import extract_entities_relations

logger = logging.getLogger(__name__)


async def _persist_entities_and_relations(
    book_id: str,
    entities: list,
    relations: list,
    http_client: Any,
) -> None:
    """通过 HTTP 将提取的实体和关系持久化到 RAG 服务，供全局图重建使用。

    先前直接使用 Repository 写库，现已改为 HTTP 调用 RAG 服务，
    为后续知识库独立部署做准备。
    """
    if not entities:
        return

    # 实体列表转为 dict 列表
    entity_dicts = []
    for e in entities:
        entity_dicts.append({
            "name": e.name,
            "entity_type": e.entity_type,
            "description": e.description or "",
            "aliases": e.aliases if e.aliases else None,
            "chunk_ids": e.chunk_ids if e.chunk_ids else None,
        })

    count = await http_client.upsert_entities(book_id, entity_dicts)
    logger.info(f"持久化 {count} 个实体 (book_id={book_id}, HTTP)")

    # 关系列表转为 dict 列表（使用实体名，服务端解析 ID）
    if relations:
        rel_dicts = []
        for r in relations:
            rel_dicts.append({
                "source_entity_name": r.source,
                "target_entity_name": r.target,
                "relation_type": r.relation_type,
                "description": r.description or "",
                "confidence": r.confidence,
            })

        count = await http_client.insert_relations(book_id, rel_dicts)
        logger.info(f"持久化 {count} 条关系 (book_id={book_id}, HTTP)")


async def build_graph_for_book(
    book_id: str,
    chunks: list[Any],
    topics_per_chunk: list[list[str]],
    http_client: Any,
    entity_repo: Any = None,
    relation_repo: Any = None,
    model_name: str = "qwen3.5-27b",
) -> dict:
    """完整导入流水线：为单本书构建知识图谱 + 层级社区树。

    Args:
        book_id: 书籍 ID (UUID 字符串，与 DocumentRecord.id 一致)
        chunks: 文档块列表（Node 对象）
        topics_per_chunk: 每个块的 topic 标签列表
        http_client: RagHttpClient 实例（用于 HTTP 调用图谱写入端点）
        entity_repo: (已废弃，保留参数兼容性)
        relation_repo: (已废弃，保留参数兼容性)
        model_name: 实体提取用的 LLM 模型

    Returns:
        结果摘要 dict: {book_id, entity_count, relation_count, node_count, community_count, leaf_count}
    """
    result = {
        "book_id": book_id,
        "entity_count": 0,
        "relation_count": 0,
        "node_count": 0,
        "community_count": 0,
        "leaf_count": 0,
        "error": None,
    }

    # Step 1: 实体提取
    logger.info(f"开始为书籍 {book_id} 构建知识图谱...")
    entities, relations = await extract_entities_relations(
        book_id=str(book_id),
        chunks=chunks,
        topics_per_chunk=topics_per_chunk,
        model_name=model_name,
    )
    result["entity_count"] = len(entities)
    result["relation_count"] = len(relations)

    if not entities:
        logger.warning(f"书籍 {book_id} 无实体，跳过图构建")
        return result

    # Step 2: 持久化实体和关系（供全局图重建使用），通过 HTTP 调用 RAG 服务
    try:
        await _persist_entities_and_relations(
            book_id, entities, relations, http_client
        )
    except Exception as e:
        logger.warning(f"实体/关系持久化失败（不影响树构建）: {e}")

    # Step 3: 图构建 + 社区检测
    try:
        G = await asyncio.to_thread(build_graph, entities, relations)
        partition, dendrogram = await asyncio.to_thread(detect_communities, G)

        if not partition:
            logger.warning(f"书籍 {book_id} 社区检测返回空")
            return result

        # Step 4: 层级树构建（CPU 密集）
        tree_nodes, tree_edges = await asyncio.to_thread(dendrogram_to_tree,
            G=G,
            partition=partition,
            dendrogram=dendrogram if dendrogram else [],
            book_id=book_id,
        )

        # Step 5: 关联块到叶子社区
        tree_nodes = assign_chunks_to_communities(tree_nodes, entities)

        # Step 6: 通过 HTTP 存储社区树到 RAG 服务
        node_count = await store_community_tree(
            book_id=book_id,
            tree_nodes=tree_nodes,
            tree_edges=tree_edges,
            http_client=http_client,
        )

        leaf_count = sum(1 for n in tree_nodes if n.get("is_leaf"))
        community_count = len(set(partition.values()))

        result["node_count"] = node_count
        result["community_count"] = community_count
        result["leaf_count"] = leaf_count

        logger.info(
            f"书籍 {book_id} 图谱构建完成: "
            f"{result['entity_count']} 实体, {result['relation_count']} 关系, "
            f"{community_count} 社区, {leaf_count} 叶子, {node_count} 树节点"
        )
    except Exception as e:
        logger.exception(f"书籍 {book_id} 图构建/社区检测失败: {e}")
        result["error"] = str(e)[:200]

    return result
