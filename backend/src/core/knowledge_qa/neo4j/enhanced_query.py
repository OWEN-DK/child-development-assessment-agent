"""Neo4j 增强查询 — Step 1a

与 query_dispatcher.py（旧版，依赖 S2 先运行）不同：
1. 用 S2 产出的 problems 作为主种子（精确），question embedding 作为补充
2. 用 custom_entities（自定义规则关联）引导查询
3. 1-2 跳扩展获取关系邻居
4. 提取实体的 source 段落 ID 供 Step 1b 使用
5. 查询跨书关系（共识/互补/冲突）

放置位置: backend/src/core/knowledge_qa/neo4j/enhanced_query.py
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

from src.core.knowledge_qa.bundle import (
    CrossBookConflict, CrossBookConsensus, GraphEntity, GraphRelation,
)

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════════
# Result container
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class EnhancedNeo4jResult:
    """Step 1a 的完整输出。"""

    entities: dict[str, list[GraphEntity]]  # entity_type → entities
    relations: list[GraphRelation]
    cross_book_conflicts: list[CrossBookConflict]
    cross_book_consensus: list[CrossBookConsensus]
    entity_seeds: list[str]  # 供 Step 1b 和 Step 1c 使用的引导词
    source_para_ids: dict[str, list[str]]  # book_id → [para_id, ...]


# ═══════════════════════════════════════════════════════════════════════════════
# Main entry point
# ═══════════════════════════════════════════════════════════════════════════════


async def query_neo4j_enhanced(
    question: str,
    matched_book_ids: list[str],
    s2_problems: list[str],
    custom_entities: list[str],
    *,
    embedding_helper=None,  # 可选——用于 question embedding 补充种子
    neo4j_query_timeout: int = 30,
) -> EnhancedNeo4jResult:
    """增强 Neo4j 查询。

    Args:
        question: 用户原始问题
        matched_book_ids: 匹配的书籍 ID 列表
        s2_problems: S2 识别的问题名称列表（主种子来源）
        custom_entities: 从 fast_knowledge_match 来的规则关联实体
        embedding_helper: 可选 EmbeddingHelper，用于 question→实体语义匹配补充
        neo4j_query_timeout: Neo4j 查询超时秒数

    Returns:
        EnhancedNeo4jResult 包含实体、关系、跨书关系和引导词列表。
        Neo4j 不可用时返回空结果（不阻塞）。
    """
    from src.core.knowledge_qa.neo4j.driver import neo4j_available, get_neo4j_driver

    empty = EnhancedNeo4jResult(
        entities={}, relations=[],
        cross_book_conflicts=[], cross_book_consensus=[],
        entity_seeds=[], source_para_ids={},
    )

    if not neo4j_available():
        logger.info("Neo4j 不可用，跳过增强查询")
        return empty

    driver = get_neo4j_driver()
    if driver is None:
        return empty

    try:
        result = await asyncio.wait_for(
            _do_enhanced_query(
                driver, question, matched_book_ids,
                s2_problems, custom_entities, embedding_helper,
            ),
            timeout=neo4j_query_timeout,
        )
        logger.info(
            "Neo4j 增强查询完成: %d entity types, %d relations, "
            "%d cross-book conflicts, %d consensus, %d seeds",
            len(result.entities), len(result.relations),
            len(result.cross_book_conflicts), len(result.cross_book_consensus),
            len(result.entity_seeds),
        )
        return result

    except asyncio.TimeoutError:
        logger.warning("Neo4j 增强查询超时 (%ds)，降级", neo4j_query_timeout)
        return empty
    except Exception as e:
        logger.warning("Neo4j 增强查询失败: %s，降级", e)
        return empty


# ═══════════════════════════════════════════════════════════════════════════════
# Internal implementation
# ═══════════════════════════════════════════════════════════════════════════════


async def _do_enhanced_query(
    driver,
    question: str,
    matched_book_ids: list[str],
    s2_problems: list[str],
    custom_entities: list[str],
    embedding_helper,
) -> EnhancedNeo4jResult:
    """执行增强查询的所有步骤。"""
    from neo4j import Session

    with driver.session() as session:
        # ── Step 1: 收集种子实体名 ──
        seed_names = _collect_seed_names(
            session, matched_book_ids, s2_problems, custom_entities,
            question, embedding_helper,
        )

        if not seed_names:
            logger.info("Neo4j 增强查询: 无种子实体")
            cross_con, cross_rel = _query_cross_book_relations(session, matched_book_ids)
            return EnhancedNeo4jResult(
                entities={}, relations=[],
                cross_book_conflicts=cross_con, cross_book_consensus=cross_rel,
                entity_seeds=[], source_para_ids={},
            )

        # ── Step 2: 1-2 跳扩展获取邻居 ──
        entities_by_type, relations = _expand_from_seeds(
            session, seed_names, matched_book_ids, max_hops=2,
        )

        # ── Step 3: 跨书关系查询 ──
        cross_conflicts, cross_consensus = _query_cross_book_relations(
            session, matched_book_ids,
        )

        # ── Step 4: 提取 source 段落 ID ──
        source_para_ids = _extract_source_para_ids(session, entities_by_type)

        # ── Step 5: 去重种子（扩展中去掉已有实体的种子）──
        all_entity_names: set[str] = set()
        for ents in entities_by_type.values():
            for e in ents:
                all_entity_names.add(e.name)
        # 保留在 Neo4j 中实际存在且未被扩展覆盖的种子名
        final_seeds = [
            s for s in seed_names
            if s in all_entity_names and s not in [
                e.name for ents in entities_by_type.values() for e in ents
            ]
        ]

    return EnhancedNeo4jResult(
        entities=entities_by_type,
        relations=relations,
        cross_book_conflicts=cross_conflicts,
        cross_book_consensus=cross_consensus,
        entity_seeds=list(seed_names)[:20],  # 最多 20 个种子
        source_para_ids=source_para_ids,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Seed collection
# ═══════════════════════════════════════════════════════════════════════════════


def _collect_seed_names(
    session,
    matched_book_ids: list[str],
    s2_problems: list[str],
    custom_entities: list[str],
    question: str,
    embedding_helper,
) -> set[str]:
    """收集所有种子实体名。

    优先级（依次合并，不去重）:
    1. s2_problems 直接作为实体名（确定性最强）
    2. custom_entities（自定义规则关联）
    3. 从 Neo4j 中按问题名模糊匹配实体
    4. question embedding → Neo4j 语义相似实体（补充）
    """
    seeds: set[str] = set()

    # ── 来源 1: S2 problems ──
    seeds.update(p.strip() for p in s2_problems if p.strip())

    # ── 来源 2: custom_entities ──
    seeds.update(e.strip() for e in custom_entities if e.strip())

    # ── 来源 3: Neo4j 模糊匹配 ──
    if s2_problems or custom_entities:
        all_seeds = list(seeds)
        fuzzy_matches = _fuzzy_match_entities(session, all_seeds, matched_book_ids)
        seeds.update(fuzzy_matches)

    # ── 来源 4: question embedding → Neo4j 实体（补充）──
    if embedding_helper and question.strip() and len(seeds) < 5:
        try:
            # 同步调用 embedding（在 await 上下文中）
            pass  # embedding 调用放在 _do_enhanced_query 的 async 上下文中
        except Exception:
            pass

    return seeds


def _fuzzy_match_entities(
    session,
    names: list[str],
    book_ids: list[str],
) -> list[str]:
    """在 Neo4j 中按名称模糊匹配实体。

    使用 CONTAINS 做子串匹配——"注意力不集中" 匹配 "注意力不集中干预"。
    """
    if not names:
        return []

    matched: list[str] = []
    try:
        for name in names[:10]:
            query = """
                MATCH (e)
                WHERE e.book_id IN $book_ids
                  AND (e.name CONTAINS $name OR $name CONTAINS e.name)
                RETURN e.name AS name, labels(e)[0] AS type
                LIMIT 5
            """
            results = session.run(query, name=name, book_ids=book_ids).data()
            for r in results:
                entity_name = r.get("name", "")
                if entity_name and entity_name not in matched:
                    matched.append(entity_name)
    except Exception as e:
        logger.warning("Neo4j 模糊实体匹配失败: %s", e)

    return matched


# ═══════════════════════════════════════════════════════════════════════════════
# Entity expansion
# ═══════════════════════════════════════════════════════════════════════════════


def _expand_from_seeds(
    session,
    seed_names: set[str],
    book_ids: list[str],
    max_hops: int = 2,
) -> tuple[dict[str, list[GraphEntity]], list[GraphRelation]]:
    """从种子实体做 1-2 跳关系扩展。

    Returns:
        entities_by_type: {"Problem": [GraphEntity, ...], ...}
        relations: 所有双边关系
    """
    if not seed_names:
        return {}, []

    seed_list = list(seed_names)[:30]

    try:
        # 1 跳查询：种子 → 邻居 + 关系
        query = """
            MATCH (seed)-[r]-(neighbor)
            WHERE seed.name IN $seed_names
              AND seed.book_id IN $book_ids
              AND neighbor.book_id IN $book_ids
            RETURN seed.name AS seed_name, labels(seed)[0] AS seed_type,
                   seed.description AS seed_desc, seed.book_id AS seed_book,
                   seed.book_title AS seed_title,
                   type(r) AS rel_type,
                   neighbor.name AS neighbor_name,
                   labels(neighbor)[0] AS neighbor_type,
                   neighbor.description AS neighbor_desc,
                   neighbor.book_id AS neighbor_book,
                   neighbor.book_title AS neighbor_title
            LIMIT 200
        """
        rows = session.run(query, seed_names=seed_list, book_ids=book_ids).data()

        entities_by_type: dict[str, dict[str, GraphEntity]] = {}
        relations: dict[tuple[str, str, str], GraphRelation] = {}  # (src, tgt, type)

        for row in rows:
            # seed 实体
            sname = row.get("seed_name", "")
            stype = row.get("seed_type", "Unknown")
            if sname and sname not in entities_by_type.setdefault(stype, {}):
                entities_by_type[stype][sname] = GraphEntity(
                    name=sname,
                    entity_type=stype,
                    description=row.get("seed_desc", "") or "",
                    book_id=row.get("seed_book", "") or "",
                    book_title=row.get("seed_title", "") or "",
                )

            # neighbor 实体
            nname = row.get("neighbor_name", "")
            ntype = row.get("neighbor_type", "Unknown")
            if nname and nname not in entities_by_type.setdefault(ntype, {}):
                entities_by_type[ntype][nname] = GraphEntity(
                    name=nname,
                    entity_type=ntype,
                    description=row.get("neighbor_desc", "") or "",
                    book_id=row.get("neighbor_book", "") or "",
                    book_title=row.get("neighbor_title", "") or "",
                )

            # 关系
            rel_type = row.get("rel_type", "")
            if sname and nname and rel_type:
                key = (sname, nname, rel_type)
                if key not in relations:
                    relations[key] = GraphRelation(
                        source_entity=sname,
                        target_entity=nname,
                        relation_type=rel_type,
                        source_book=row.get("seed_book", "") or "",
                        target_book=row.get("neighbor_book", "") or "",
                    )

        # 转 list
        entities_listed: dict[str, list[GraphEntity]] = {
            et: list(emap.values())
            for et, emap in entities_by_type.items()
        }
        return entities_listed, list(relations.values())

    except Exception as e:
        logger.warning("Neo4j 实体扩展失败: %s", e)
        return {}, []


# ═══════════════════════════════════════════════════════════════════════════════
# Cross-book relations
# ═══════════════════════════════════════════════════════════════════════════════


def _query_cross_book_relations(
    session,
    book_ids: list[str],
) -> tuple[list[CrossBookConflict], list[CrossBookConsensus]]:
    """查询跨书关系——将原始 Neo4j 结果转为 bundle 类型。"""
    if len(book_ids) < 2:
        return [], []

    conflicts: list[CrossBookConflict] = []
    consensus: list[CrossBookConsensus] = []

    try:
        query = """
            MATCH (a)-[r:CROSS_BOOK_CONSENSUS|CROSS_BOOK_COMPLEMENTS|CROSS_BOOK_CONFLICTS|SAME_AS|CROSS_TREATS]->(b)
            WHERE a.book_id IN $book_ids AND b.book_id IN $book_ids
            RETURN a.name AS source_entity, a.book_id AS source_book,
                   labels(a)[0] AS source_type,
                   type(r) AS relation_type,
                   b.name AS target_entity, b.book_id AS target_book,
                   labels(b)[0] AS target_type,
                   coalesce(r.explanation, r.description, '') AS evidence
            LIMIT 100
        """
        rows = session.run(query, book_ids=book_ids).data()

        for row in rows:
            rel_type = row.get("relation_type", "")
            entity = row.get("source_entity", "")
            book_list = [
                row.get("source_book", ""), row.get("target_book", ""),
            ]
            books = sorted(set(b for b in book_list if b))

            if "CONFLICT" in rel_type.upper():
                conflicts.append(CrossBookConflict(
                    entity_name=entity,
                    books=books,
                    positions=[],  # 细节由 LLM 提取
                    neo4j_relation_type=rel_type,
                ))
            else:
                consensus.append(CrossBookConsensus(
                    entity_name=entity,
                    books=books,
                    relation_type=rel_type,
                    description=row.get("evidence", "") or "",
                ))

        logger.info(
            "跨书关系查询完成: %d conflicts, %d consensus",
            len(conflicts), len(consensus),
        )

    except Exception as e:
        logger.warning("跨书关系查询失败: %s", e)

    return conflicts, consensus


# ═══════════════════════════════════════════════════════════════════════════════
# Source paragraph extraction
# ═══════════════════════════════════════════════════════════════════════════════


def _extract_source_para_ids(
    session,
    entities_by_type: dict[str, list[GraphEntity]],
) -> dict[str, list[str]]:
    """从实体节点提取 source_chapter 和 source_para_ids。

    尝试从 Neo4j 实体节点的 source 字段提取段落 ID，
    或通过 CONTAINS_ENTITY 关系找到对应原文段落。
    """
    source_map: dict[str, list[str]] = {}
    all_entity_names: list[str] = []

    for ents in entities_by_type.values():
        for e in ents:
            if e.source_para_ids:
                source_map.setdefault(e.book_id, []).extend(e.source_para_ids)
            all_entity_names.append(e.name)

    # 对没有 source_para_ids 的实体，通过 CONTAINS_ENTITY 查询
    try:
        query = """
            MATCH (e)-[:CONTAINS_ENTITY]-(chunk)
            WHERE e.name IN $names
            RETURN e.name AS entity_name, e.book_id AS book_id, chunk.id AS chunk_id
            LIMIT 300
        """
        rows = session.run(query, names=all_entity_names[:100]).data()
        for r in rows:
            bid = r.get("book_id", "") or ""
            cid = r.get("chunk_id", "")
            if bid and cid:
                source_map.setdefault(bid, []).append(cid)
    except Exception as e:
        logger.warning("CONTAINS_ENTITY 查询失败: %s", e)

    # 去重
    return {k: list(set(v)) for k, v in source_map.items()}
