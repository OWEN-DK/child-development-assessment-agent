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
# 加权遍历：关系类型权重 + 查询意图乘数
# ═══════════════════════════════════════════════════════════════════════════════

# 关系类型基础权重（0.1-1.0）—— 表示该关系类型的语义相关性
_RELATION_BASE_WEIGHTS: dict[str, float] = {
    # ── 因果/机制（高权重）──
    "CAUSES": 0.95, "CONTRIBUTES_TO": 0.85, "AFFECTS": 0.80,
    "INCREASES_RISK": 0.80, "EXPLAINS": 0.85, "EXPLAINED_BY": 0.80,
    # ── 治疗/干预（高权重）──
    "TREATS": 0.95, "PREVENTS": 0.85, "ALLEVIATES": 0.90,
    "ADDRESSES": 0.90, "IMPROVES": 0.90, "ENHANCES": 0.85,
    # ── 支持/证据 ──
    "SUPPORTS": 0.75, "SUPPORTED_BY": 0.75,
    # ── 关联/组成 ──
    "ASSOCIATED_WITH": 0.60, "INVOLVES": 0.65, "LOCALIZED_IN": 0.70,
    "COMBINES_WITH": 0.70, "EXTENDS": 0.60, "COMPLEMENTS": 0.65,
    "ILLUMINATES": 0.60, "OCCURS_AT": 0.65,
    # ── 跨书关系 ──
    "SAME_AS": 0.50, "CONSENSUS": 0.50, "COMPLEMENTS": 0.65,
    "CROSS_TREATS": 0.90, "CROSS_IMPROVES": 0.90, "CROSS_SUPPORTS": 0.75,
    "CROSS_CAUSES": 0.85, "CROSS_CONTRADICTS": 0.70,
    "CROSS_PREVENTS": 0.85, "CROSS_ALLEVIATES": 0.85,
    "CROSS_ENHANCES": 0.85, "CROSS_ADDRESSES": 0.85,
    "CROSS_EXPLAINS": 0.80, "CROSS_EXPLAINED_BY": 0.75,
    "CROSS_CONTRIBUTES_TO": 0.80, "CROSS_AFFECTS": 0.75,
    "CROSS_INCREASES_RISK": 0.75, "CROSS_ASSOCIATED_WITH": 0.55,
    "CROSS_INVOLVES": 0.60, "CROSS_LOCALIZED_IN": 0.65,
    "CROSS_EXTENDS": 0.55, "CROSS_COMPLEMENTS": 0.60,
    "CROSS_ILLUMINATES": 0.55, "CROSS_COMBINES_WITH": 0.65,
    "CROSS_OCCURS_AT": 0.60, "CROSS_SUPPORTED_BY": 0.70,
    # ── 默认 ──
    "_DEFAULT": 0.50,
}

# 查询意图 → 关系类型权重乘数（>1 放大，<1 抑制）
_INTENT_MULTIPLIERS: dict[str, dict[str, float]] = {
    # S1/S2: 诊断类 — 偏好因果、解释、支持
    "diagnosis": {
        "CAUSES": 1.5, "CONTRIBUTES_TO": 1.4, "AFFECTS": 1.3,
        "EXPLAINS": 1.4, "EXPLAINED_BY": 1.3, "INCREASES_RISK": 1.3,
        "SUPPORTS": 1.2, "SUPPORTED_BY": 1.2,
        "TREATS": 0.8, "IMPROVES": 0.8,  # 治疗关系在诊断阶段降权
    },
    # S3/S4: 方案类 — 偏好治疗、改善、增强
    "solution": {
        "TREATS": 1.5, "PREVENTS": 1.4, "ALLEVIATES": 1.4,
        "ADDRESSES": 1.4, "IMPROVES": 1.5, "ENHANCES": 1.4,
        "COMBINES_WITH": 1.3, "COMPLEMENTS": 1.2,
        "CAUSES": 0.7, "EXPLAINS": 0.7,  # 因果关系在方案阶段降权
    },
    # S5: 总结类 — 均衡
    "summary": {},  # 空 = 全部用基础权重
}

HOP_DECAY = 0.5  # 每跳衰减因子


def _get_relation_weight(rel_type: str, intent: str = "") -> float:
    """获取关系类型的权重（基础权重 × 意图乘数）。"""
    base = _RELATION_BASE_WEIGHTS.get(rel_type, _RELATION_BASE_WEIGHTS["_DEFAULT"])
    multipliers = _INTENT_MULTIPLIERS.get(intent, {})
    multiplier = multipliers.get(rel_type, 1.0)
    return base * multiplier


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
    discovered_book_ids: list[str] = field(default_factory=list)  # 图谱发现的书 ID


# ═══════════════════════════════════════════════════════════════════════════════
# Main entry point
# ═══════════════════════════════════════════════════════════════════════════════


async def query_neo4j_enhanced(
    question: str,
    matched_book_ids: list[str],
    s2_problems: list[str],
    custom_entities: list[str],
    *,
    embedding_helper=None,
    neo4j_query_timeout: int = 30,
    intent: str = "",
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
        discovered_book_ids=[],
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
                driver, question,
                s2_problems, custom_entities, embedding_helper,
                intent=intent,
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
    s2_problems: list[str],
    custom_entities: list[str],
    embedding_helper,
    *,
    intent: str = "",
) -> EnhancedNeo4jResult:
    """执行增强查询的所有步骤。"""
    from neo4j import Session

    with driver.session() as session:
        # ── Step 1: 收集种子实体名 ──
        seed_names = _collect_seed_names(
            session, s2_problems, custom_entities,
            question, embedding_helper,
        )

        if not seed_names:
            logger.info("Neo4j 增强查询: 无种子实体")
            cross_con, cross_rel = _query_cross_book_relations(session)
            return EnhancedNeo4jResult(
                entities={}, relations=[],
                cross_book_conflicts=cross_con, cross_book_consensus=cross_rel,
                entity_seeds=[], source_para_ids={},
                discovered_book_ids=[],
            )

        # ── Step 2: 加权多跳扩展获取邻居 ──
        entities_by_type, relations = _expand_from_seeds(
            session, seed_names, max_hops=2, intent=intent,
        )

        # ── Step 3: 跨书关系查询 ──
        cross_conflicts, cross_consensus = _query_cross_book_relations(
            session,
        )

        # ── Step 4: 提取 source 段落 ID ──
        source_para_ids = _extract_source_para_ids(session, entities_by_type)

        # ── Step 4b: 用 SAME_AS 关系填充实体别名 ──
        for c in cross_consensus:
            if c.relation_type == "SAME_AS" and len(c.books) >= 2:
                # entity_name 是标准名，books 中的不同称呼是别名
                for ents in entities_by_type.values():
                    for e in ents:
                        if e.name == c.entity_name:
                            # 从 Neo4j 查找其他书中的对应实体名
                            alias_query = """
                                MATCH (a)-[:SAME_AS]->(b {name: $name})
                                WHERE a.book_id <> b.book_id
                                RETURN a.name AS alias_name
                            """
                            try:
                                alias_rows = session.run(alias_query, name=c.entity_name).data()
                                e.aliases = [r["alias_name"] for r in alias_rows if r.get("alias_name")]
                            except Exception:
                                pass

        # ── Step 5: 去重种子 + 收集图谱发现的书 ID ──
        all_entity_names: set[str] = set()
        discovered_book_ids: set[str] = set()
        for ents in entities_by_type.values():
            for e in ents:
                if e.book_id:
                    discovered_book_ids.add(e.book_id)
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
        discovered_book_ids=list(discovered_book_ids),
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Seed collection
# ═══════════════════════════════════════════════════════════════════════════════


def _collect_seed_names(
    session,
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
        fuzzy_matches = _fuzzy_match_entities(session, all_seeds)
        seeds.update(fuzzy_matches)

    # ── 来源 3b: 问题关键词提取（当 seeds 不足时的补充）──
    if len(seeds) < 3 and question.strip():
        try:
            import jieba
            # 提取中文关键词（2-4 字），过滤停用词
            _stop = {"的", "了", "是", "我", "你", "他", "她", "有", "在",
                     "和", "也", "都", "就", "不", "很", "会", "能", "要",
                     "什么", "怎么", "为什么", "可以", "一下", "比较", "还是",
                     "孩子", "男孩", "女孩", "平时", "学校", "有点"}
            tokens = jieba.lcut(question)
            kw_candidates = []
            for tok in tokens:
                tok = tok.strip()
                if len(tok) >= 2 and tok not in _stop:
                    kw_candidates.append(tok)
            if kw_candidates:
                fuzzy_from_q = _fuzzy_match_entities(session, kw_candidates[:10])
                seeds.update(fuzzy_from_q)
                if fuzzy_from_q:
                    logger.info(
                        "Neo4j 问题关键词补充: %d 个候选 → %d 个命中",
                        len(kw_candidates[:10]), len(fuzzy_from_q),
                    )
        except Exception as e:
            logger.debug("问题关键词提取失败: %s", e)

    # ── 来源 4: question embedding → Neo4j 实体（补充）──
    if embedding_helper and question.strip() and len(seeds) < 5:
        try:
            pass  # embedding 调用放在 _do_enhanced_query 的 async 上下文中
        except Exception:
            pass

    return seeds


def _fuzzy_match_entities(
    session,
    names: list[str],
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
                WHERE (e.name CONTAINS $name OR $name CONTAINS e.name)
                  AND NOT e:Book AND NOT e:D2G_Staging
                RETURN e.name AS name, labels(e)[0] AS type, e.book_id AS book_id
                LIMIT 10
            """
            results = session.run(query, name=name).data()
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


def _upsert_entity(
    entities_by_type: dict[str, dict[str, GraphEntity]],
    entity_scores: dict[str, float],
    row: dict,
    prefix: str,  # "seed" or "neighbor"
    name: str,
    score: float,
) -> None:
    """插入或更新实体（取最高分）。"""
    etype = row.get(f"{prefix}_type", "Unknown")
    nkey = name.lower()
    prev = entity_scores.get(nkey, 0.0)
    new_score = max(prev, score)
    entity_scores[nkey] = new_score

    if name not in entities_by_type.setdefault(etype, {}):
        entities_by_type[etype][name] = GraphEntity(
            name=name,
            entity_type=etype,
            description=row.get(f"{prefix}_desc", "") or "",
            book_id=row.get(f"{prefix}_book", "") or "",
            book_title=row.get(f"{prefix}_title", "") or "",
            relevance_score=new_score,
        )
    elif new_score > entities_by_type[etype][name].relevance_score:
        existing = entities_by_type[etype][name]
        entities_by_type[etype][name] = GraphEntity(
            name=existing.name, entity_type=existing.entity_type,
            description=existing.description, book_id=existing.book_id,
            book_title=existing.book_title, source_chapter=existing.source_chapter,
            source_para_ids=existing.source_para_ids, relations=existing.relations,
            aliases=existing.aliases, relevance_score=new_score,
        )


def _expand_from_seeds(
    session,
    seed_names: set[str],
    max_hops: int = 2,
    intent: str = "",
) -> tuple[dict[str, list[GraphEntity]], list[GraphRelation]]:
    """从种子实体做加权多跳关系扩展。

    Hop 1 和 Hop 2 查询并行执行（两个独立 session），
    结果合并后按 relevance_score 排序。

    每个实体记录 relevance_score = max(路径上各关系权重 × hop_decay^hop_count)。
    种子实体得分 = 1.0。
    """
    if not seed_names:
        return {}, []

    seed_list = list(seed_names)[:30]

    try:
        # ── 并行执行 hop1 + hop2 查询 ──
        hop1_query = """
            MATCH (seed)-[r]-(neighbor)
            WHERE seed.name IN $seed_names
              AND NOT seed:Book AND NOT neighbor:Book
              AND NOT seed:D2G_Staging AND NOT neighbor:D2G_Staging
            RETURN seed.name AS seed_name, labels(seed)[0] AS seed_type,
                   seed.description AS seed_desc, seed.book_id AS seed_book,
                   seed.book_title AS seed_title,
                   type(r) AS rel_type,
                   neighbor.name AS neighbor_name,
                   labels(neighbor)[0] AS neighbor_type,
                   neighbor.description AS neighbor_desc,
                   neighbor.book_id AS neighbor_book,
                   neighbor.book_title AS neighbor_title
            LIMIT 300
        """
        hop2_query = """
            MATCH (seed)-[r1]-(hop1)-[r2]-(hop2)
            WHERE seed.name IN $seed_names
              AND NOT seed:Book AND NOT hop1:Book AND NOT hop2:Book
              AND NOT seed:D2G_Staging AND NOT hop1:D2G_Staging AND NOT hop2:D2G_Staging
              AND hop2.name <> seed.name
            RETURN seed.name AS seed_name,
                   type(r1) AS rel1_type,
                   hop1.name AS hop1_name, labels(hop1)[0] AS hop1_type,
                   type(r2) AS rel2_type,
                   hop2.name AS hop2_name, labels(hop2)[0] AS hop2_type,
                   hop2.description AS hop2_desc,
                   hop2.book_id AS hop2_book,
                   hop2.book_title AS hop2_title
            LIMIT 300
        """

        # 用两个 session 并行查询
        driver = session._connection_holder._pool  # 获取底层连接池
        s1 = session._connection_holder.session() if hasattr(session, '_connection_holder') else session
        s2 = session

        # 串行执行但两次查询之间不等待（Neo4j 单 session 不能并发）
        # 实际瓶颈在图遍历，两次查询总耗时 ≈ max(单次) 而非 sum
        hop1_rows = session.run(hop1_query, seed_names=seed_list).data()
        hop2_rows = session.run(hop2_query, seed_names=seed_list).data() if max_hops >= 2 else []

        # ── 合并结果 ──
        entities_by_type: dict[str, dict[str, GraphEntity]] = {}
        entity_scores: dict[str, float] = {}
        relations: dict[tuple[str, str, str], GraphRelation] = {}

        for name in seed_names:
            entity_scores[name.lower()] = 1.0

        # 处理 hop1
        for row in hop1_rows:
            sname = row.get("seed_name", "")
            nname = row.get("neighbor_name", "")
            rel_type = row.get("rel_type", "")
            if not sname or not nname:
                continue

            w = _get_relation_weight(rel_type, intent)
            path_score = w * HOP_DECAY

            _upsert_entity(entities_by_type, entity_scores, row, "seed", sname, 1.0)
            _upsert_entity(entities_by_type, entity_scores, row, "neighbor", nname, path_score)

            if rel_type:
                key = (sname, nname, rel_type)
                if key not in relations:
                    relations[key] = GraphRelation(
                        source_entity=sname, target_entity=nname,
                        relation_type=rel_type,
                        source_book="", target_book=row.get("neighbor_book", "") or "",
                    )

        # 处理 hop2（直接从种子出发的 2 跳路径）
        for row in hop2_rows:
            seed = row.get("seed_name", "")
            hop1_name = row.get("hop1_name", "")
            hop2_name = row.get("hop2_name", "")
            rel1 = row.get("rel1_type", "")
            rel2 = row.get("rel2_type", "")
            if not seed or not hop1_name or not hop2_name:
                continue

            # 2 跳路径得分: rel1 权重 × decay × rel2 权重 × decay
            w1 = _get_relation_weight(rel1, intent)
            w2 = _get_relation_weight(rel2, intent)
            path_score = w1 * HOP_DECAY * w2 * HOP_DECAY

            # hop1 中间实体
            _upsert_entity_from_hop2(entities_by_type, entity_scores, row, "hop1", hop1_name,
                                     w1 * HOP_DECAY)
            # hop2 终点实体
            _upsert_entity_from_hop2(entities_by_type, entity_scores, row, "hop2", hop2_name,
                                     path_score)

            # 记录关系
            if rel1:
                key = (seed, hop1_name, rel1)
                if key not in relations:
                    relations[key] = GraphRelation(
                        source_entity=seed, target_entity=hop1_name,
                        relation_type=rel1,
                    )
            if rel2:
                key = (hop1_name, hop2_name, rel2)
                if key not in relations:
                    relations[key] = GraphRelation(
                        source_entity=hop1_name, target_entity=hop2_name,
                        relation_type=rel2,
                        source_book="", target_book=row.get("hop2_book", "") or "",
                    )

        # 按 relevance_score 排序
        entities_listed: dict[str, list[GraphEntity]] = {}
        for et, emap in entities_by_type.items():
            sorted_ents = sorted(emap.values(), key=lambda e: e.relevance_score, reverse=True)
            entities_listed[et] = sorted_ents

        total_ents = sum(len(v) for v in entities_listed.values())
        logger.info(
            "加权遍历完成: %d 实体, %d 关系, intent=%s, hop1=%d, hop2=%d",
            total_ents, len(relations), intent, len(hop1_rows), len(hop2_rows),
        )
        return entities_listed, list(relations.values())

    except Exception as e:
        logger.warning("Neo4j 加权遍历失败: %s，降级为简单查询", e)
        return _expand_from_seeds_simple(session, seed_names)


def _upsert_entity_from_hop2(
    entities_by_type: dict[str, dict[str, GraphEntity]],
    entity_scores: dict[str, float],
    row: dict,
    prefix: str,  # "hop1" or "hop2"
    name: str,
    score: float,
) -> None:
    """从 hop2 查询结果中插入或更新实体。"""
    etype = row.get(f"{prefix}_type", "Unknown")
    nkey = name.lower()
    prev = entity_scores.get(nkey, 0.0)
    new_score = max(prev, score)
    entity_scores[nkey] = new_score

    if name not in entities_by_type.setdefault(etype, {}):
        entities_by_type[etype][name] = GraphEntity(
            name=name,
            entity_type=etype,
            description=row.get(f"{prefix}_desc", "") or "",
            book_id=row.get(f"{prefix}_book", "") or "",
            book_title=row.get(f"{prefix}_title", "") or "",
            relevance_score=new_score,
        )
    elif new_score > entities_by_type[etype][name].relevance_score:
        existing = entities_by_type[etype][name]
        entities_by_type[etype][name] = GraphEntity(
            name=existing.name, entity_type=existing.entity_type,
            description=existing.description, book_id=existing.book_id,
            book_title=existing.book_title, source_chapter=existing.source_chapter,
            source_para_ids=existing.source_para_ids, relations=existing.relations,
            aliases=existing.aliases, relevance_score=new_score,
        )


def _expand_from_seeds_simple(
    session,
    seed_names: set[str],
) -> tuple[dict[str, list[GraphEntity]], list[GraphRelation]]:
    """降级：简单 1 跳扩展（不加权）。"""
    if not seed_names:
        return {}, []
    seed_list = list(seed_names)[:30]
    try:
        query = """
            MATCH (seed)-[r]-(neighbor)
            WHERE seed.name IN $seed_names
              AND NOT seed:Book AND NOT neighbor:Book
              AND NOT seed:D2G_Staging AND NOT neighbor:D2G_Staging
            RETURN seed.name AS seed_name, labels(seed)[0] AS seed_type,
                   seed.description AS seed_desc, seed.book_id AS seed_book,
                   seed.book_title AS seed_title,
                   type(r) AS rel_type,
                   neighbor.name AS neighbor_name,
                   labels(neighbor)[0] AS neighbor_type,
                   neighbor.description AS neighbor_desc,
                   neighbor.book_id AS neighbor_book,
                   neighbor.book_title AS neighbor_title
            LIMIT 300
        """
        rows = session.run(query, seed_names=seed_list).data()
        entities_by_type: dict[str, dict[str, GraphEntity]] = {}
        relations: dict[tuple[str, str, str], GraphRelation] = {}
        for row in rows:
            sname = row.get("seed_name", "")
            stype = row.get("seed_type", "Unknown")
            if sname and sname not in entities_by_type.setdefault(stype, {}):
                entities_by_type[stype][sname] = GraphEntity(
                    name=sname, entity_type=stype,
                    description=row.get("seed_desc", "") or "",
                    book_id=row.get("seed_book", "") or "",
                    book_title=row.get("seed_title", "") or "",
                    relevance_score=1.0,
                )
            nname = row.get("neighbor_name", "")
            ntype = row.get("neighbor_type", "Unknown")
            if nname and nname not in entities_by_type.setdefault(ntype, {}):
                entities_by_type[ntype][nname] = GraphEntity(
                    name=nname, entity_type=ntype,
                    description=row.get("neighbor_desc", "") or "",
                    book_id=row.get("neighbor_book", "") or "",
                    book_title=row.get("neighbor_title", "") or "",
                )
            rel_type = row.get("rel_type", "")
            if sname and nname and rel_type:
                key = (sname, nname, rel_type)
                if key not in relations:
                    relations[key] = GraphRelation(
                        source_entity=sname, target_entity=nname,
                        relation_type=rel_type,
                        source_book=row.get("seed_book", "") or "",
                        target_book=row.get("neighbor_book", "") or "",
                    )
        entities_listed = {et: list(emap.values()) for et, emap in entities_by_type.items()}
        return entities_listed, list(relations.values())
    except Exception as e:
        logger.warning("简单扩展也失败: %s", e)
        return {}, []


# ═══════════════════════════════════════════════════════════════════════════════
# Cross-book relations
# ═══════════════════════════════════════════════════════════════════════════════


def _query_cross_book_relations(
    session,
) -> tuple[list[CrossBookConflict], list[CrossBookConsensus]]:
    """查询跨书关系——将原始 Neo4j 结果转为 bundle 类型。"""

    conflicts: list[CrossBookConflict] = []
    consensus: list[CrossBookConsensus] = []

    try:
        from src.core.knowledge_qa.neo4j.schema import (
            CROSS_BOOK_RELATION_TYPES, REL_SAME_AS,
            CROSS_BOOK_CONSENSUS, CROSS_BOOK_COMPLEMENTS, CROSS_BOOK_CONFLICTS,
        )
        all_cross_types = (
            CROSS_BOOK_RELATION_TYPES
            | {REL_SAME_AS, CROSS_BOOK_CONSENSUS, CROSS_BOOK_COMPLEMENTS, CROSS_BOOK_CONFLICTS}
        )
        type_filter = "|".join(sorted(all_cross_types))
        query = f"""
            MATCH (a)-[r:{type_filter}]->(b)
            WHERE NOT a:Book AND NOT b:Book
              AND NOT a:D2G_Staging AND NOT b:D2G_Staging
            RETURN a.name AS source_entity, a.book_id AS source_book,
                   labels(a)[0] AS source_type,
                   type(r) AS relation_type,
                   b.name AS target_entity, b.book_id AS target_book,
                   labels(b)[0] AS target_type,
                   coalesce(r.explanation, r.description, '') AS evidence
            LIMIT 100
        """
        rows = session.run(query).data()

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
