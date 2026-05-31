"""全局图重建 — 跨书实体去重 + 全局社区树

定期执行：加载所有书的实体和关系 → 名称去重合并 → Louvain 社区检测 → 全局层级树存储。
"""

import asyncio
import logging
import time
from typing import Any

from sqlalchemy.ext.asyncio import async_sessionmaker

from src.core.knowledge_qa.graph.builder import (
    assign_chunks_to_communities,
    build_graph,
    dendrogram_to_tree,
    store_community_tree,
)
from src.core.knowledge_qa.graph.community import detect_communities
from src.core.knowledge_qa.graph.extractor import Entity, Relation
from src.repository.graph_repository import (
    GraphCommunityRepository,
    GraphEntityRepository,
    GraphRelationRepository,
)

logger = logging.getLogger(__name__)


def _merge_entities_by_name(all_entities: list) -> list[Entity]:
    """跨书同名实体合并：合并 chunk_ids、aliases，保留最长 description。"""
    merged: dict[str, Entity] = {}

    for e in all_entities:
        name = e.name
        if name in merged:
            existing = merged[name]
            # 合并 chunk_ids
            existing.chunk_ids = list(dict.fromkeys(
                str(c) for c in (existing.chunk_ids or []) + (e.chunk_ids or [])
            ))
            # 合并 aliases
            if e.aliases:
                existing.aliases = list(dict.fromkeys(
                    (existing.aliases or []) + e.aliases
                ))
            # 保留最长描述
            if e.description and (not existing.description or len(e.description) > len(existing.description)):
                existing.description = e.description
        else:
            merged[name] = Entity(
                name=name,
                entity_type=e.entity_type,
                description=e.description or "",
                aliases=e.aliases or [],
                book_id="",  # 全局实体无单一 book_id
                chunk_ids=e.chunk_ids or [],
            )

    return list(merged.values())


def _rebuild_relations_from_entities(
    merged_entities: list[Entity],
    all_entities: list,
    all_relations: list,
) -> list[Relation]:
    """根据原始关系中的实体对，在合并后的实体名集合中重建关系。

    Args:
        merged_entities: 去重合并后的全局实体列表
        all_entities: 原始实体 ORM 列表（带 id, name）
        all_relations: 原始关系 ORM 列表（带 source_entity_id, target_entity_id）
    """
    # 构建 ORM entity id → name 映射
    id_to_name: dict[int, str] = {}
    for e in all_entities:
        id_to_name[e.id] = e.name

    # 合并后实体名集合
    merged_names = {e.name for e in merged_entities}

    # 重建关系（去重）
    seen: set[tuple[str, str, str]] = set()
    result = []
    for r in all_relations:
        source_name = id_to_name.get(r.source_entity_id)
        target_name = id_to_name.get(r.target_entity_id)
        if not source_name or not target_name:
            continue
        if source_name not in merged_names or target_name not in merged_names:
            continue

        rtype = r.relation_type.value if hasattr(r.relation_type, 'value') else str(r.relation_type)
        # 有向关系去重：保留 source → target 方向，不合并反向关系
        key = (source_name, target_name, rtype)
        if key in seen:
            continue
        seen.add(key)

        result.append(Relation(
            source=source_name,
            target=target_name,
            relation_type=rtype,
            description=r.description or "",
            confidence=float(r.confidence or 1.0),
        ))

    return result


async def rebuild_global_graph(db_session_factory: async_sessionmaker) -> dict:
    """全局图重建主入口：加载 → 去重 → 图构建 → 社区检测 → 存储。

    Args:
        db_session_factory: SQLAlchemy async_sessionmaker

    Returns:
        结果摘要 dict
    """
    start = time.monotonic()
    result = {
        "total_entities": 0,
        "merged_entities": 0,
        "total_relations": 0,
        "global_relations": 0,
        "community_count": 0,
        "leaf_count": 0,
        "node_count": 0,
        "elapsed": 0,
        "error": None,
    }

    try:
        entity_repo = GraphEntityRepository(db_session_factory)
        relation_repo = GraphRelationRepository(db_session_factory)
        community_repo = GraphCommunityRepository(db_session_factory)

        # Step 1: 加载所有实体和关系（并行查询）
        all_entities, all_relations = await asyncio.gather(
            entity_repo.find_all(),
            relation_repo.find_all(),
        )
        result["total_entities"] = len(all_entities)
        result["total_relations"] = len(all_relations)

        if not all_entities:
            logger.info("无实体数据，跳过全局图重建")
            return result

        logger.info(f"全局图重建: 加载 {len(all_entities)} 实体, {len(all_relations)} 关系")

        # Step 2: 跨书同名实体去重合并
        merged_entities = _merge_entities_by_name(all_entities)
        result["merged_entities"] = len(merged_entities)

        # Step 3: 重建全局关系
        global_relations = _rebuild_relations_from_entities(
            merged_entities, all_entities, all_relations
        )
        result["global_relations"] = len(global_relations)

        logger.info(
            f"去重合并: {len(all_entities)} → {len(merged_entities)} 实体, "
            f"{len(all_relations)} → {len(global_relations)} 关系"
        )

        # Step 4: 构建全局图 + 社区检测（CPU 密集，不阻塞事件循环）
        G = await asyncio.to_thread(build_graph, merged_entities, global_relations)
        partition, dendrogram = await asyncio.to_thread(detect_communities, G)

        if not partition:
            logger.warning("全局社区检测返回空")
            return result

        # Step 5: 层级树构建（CPU 密集）
        tree_nodes, tree_edges = await asyncio.to_thread(
            dendrogram_to_tree,
            G=G,
            partition=partition,
            dendrogram=dendrogram if dendrogram else [],
            book_id="",
            scope="global",
        )

        # Step 6: 关联 chunks
        tree_nodes = assign_chunks_to_communities(tree_nodes, merged_entities)

        # Step 7: 存储
        node_count = await store_community_tree(
            book_id="",
            tree_nodes=tree_nodes,
            tree_edges=tree_edges,
            community_repo=community_repo,
            scope="global",
        )

        leaf_count = sum(1 for n in tree_nodes if n.get("is_leaf"))
        community_count = len(set(partition.values()))

        result["node_count"] = node_count
        result["community_count"] = community_count
        result["leaf_count"] = leaf_count

        elapsed = time.monotonic() - start
        result["elapsed"] = elapsed

        logger.info(
            f"全局图重建完成: {result['merged_entities']} 合并实体, "
            f"{community_count} 社区, {leaf_count} 叶子, {node_count} 节点, "
            f"耗时 {elapsed:.1f}s"
        )

    except Exception as e:
        logger.exception(f"全局图重建失败: {e}")
        result["error"] = str(e)[:200]

    return result


# ── embedding 增强合并（§08-6.1 升级） ───────────────────────

async def _merge_entities_with_embedding(
    all_entities: list,
    embedding_helper=None,
    similarity_threshold: float = 0.9,
) -> list[Entity]:
    """基于 embedding 相似度的跨书实体合并（替代纯字符串匹配）。

    当 embedding_helper 为 None 时降级为纯字符串匹配。
    """
    if not embedding_helper:
        return _merge_entities_by_name(all_entities)

    # Phase 1: 名称完全匹配的先合并
    merged = _merge_entities_by_name(all_entities)

    # Phase 2: embedding 相似度匹配
    if len(merged) < 2:
        return merged

    # 计算所有实体的 embedding
    emb_cache: dict[str, list[float]] = {}
    for e in merged:
        key = e.name.strip().lower()
        if key not in emb_cache:
            try:
                emb = await embedding_helper.embed_text(f"{e.name} {e.description[:200]}")
                if emb:
                    emb_cache[key] = emb
            except Exception:
                pass

    # 寻找高相似度对并合并
    merge_pairs: list[tuple[str, str]] = []
    for i, e1 in enumerate(merged):
        key1 = e1.name.strip().lower()
        emb1 = emb_cache.get(key1)
        if not emb1:
            continue
        for j in range(i + 1, len(merged)):
            e2 = merged[j]
            key2 = e2.name.strip().lower()
            emb2 = emb_cache.get(key2)
            if not emb2:
                continue
            sim = embedding_helper.cosine_similarity(emb1, emb2)
            if sim >= similarity_threshold:
                merge_pairs.append((e1.name, e2.name))

    # 执行合并（将 e2 合并到 e1）
    merge_map: dict[str, str] = {}  # name → canonical_name
    for name1, name2 in merge_pairs:
        canonical = merge_map.get(name1, name1)
        target = merge_map.get(name2, name2)
        if canonical != target:
            merge_map[target] = canonical

    if not merge_map:
        return merged

    # 构建合并后的实体列表
    result: dict[str, Entity] = {}
    for e in merged:
        canonical = merge_map.get(e.name, e.name)
        if canonical in result:
            existing = result[canonical]
            existing.chunk_ids = list(dict.fromkeys(
                str(c) for c in (existing.chunk_ids or []) + (e.chunk_ids or [])
            ))
            if e.aliases:
                existing.aliases = list(dict.fromkeys(
                    (existing.aliases or []) + e.aliases
                ))
            if e.description and (not existing.description or len(e.description) > len(existing.description)):
                existing.description = e.description
        else:
            result[canonical] = Entity(
                name=canonical,
                entity_type=e.entity_type,
                description=e.description or "",
                aliases=e.aliases or [],
                book_id="",
                chunk_ids=e.chunk_ids or [],
            )

    logger.info(
        "embedding 合并: %d → %d 实体 (%d 对合并)",
        len(merged), len(result), len(merge_pairs),
    )
    return list(result.values())
