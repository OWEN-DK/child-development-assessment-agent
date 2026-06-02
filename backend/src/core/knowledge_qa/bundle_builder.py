"""Phase 1: 统一检索 — 构建 KnowledgeBundle

编排: Neo4j 增强查询 (Step 1a) → Chroma 批量搜索 (Step 1b)
      → LazyGraphRAG 增强遍历 (Step 1c) → Bundle 组装 (Step 1d)

放置位置: backend/src/core/knowledge_qa/bundle_builder.py
"""

from __future__ import annotations

import asyncio
import difflib
import logging
import time
from typing import Any

from src.core.knowledge_qa.bundle import (
    BookMeta, KnowledgeBundle, Passage, PriorityConflict, RetrievalStats,
    normalize_book_title,
)
from src.core.knowledge_qa.bundle_config import get_bundle_config

logger = logging.getLogger(__name__)

# ── 可配置阈值 ──
BUNDLE_BOOK_MIN_ENTITY_HITS = 3  # 最少 Neo4j 实体命中数
BUNDLE_BOOK_MIN_PASSAGE_HITS = 5  # 最少 Chroma passage 命中数
MAX_PASSAGES_PER_BUNDLE = 120  # 全文总 passage 上限
CHROMA_RESULTS_PER_QUERY = 30  # 每 query 的 Chroma 返回条数
MAX_QUERIES = 5  # 最多搜索 query 数量


# ═══════════════════════════════════════════════════════════════════════════════
# Main entry point
# ═══════════════════════════════════════════════════════════════════════════════


async def build_knowledge_bundle(
    question: str,
    matched_book_ids: list[str],
    s2_problems: list[str],
    custom_entities: list[str],
    child_profile: dict | None = None,
    *,
    embedding_helper=None,
) -> KnowledgeBundle:
    """Phase 1: 构建完整的不可变 KnowledgeBundle。

    Args:
        question: 用户原始问题
        matched_book_ids: 匹配的书籍 ID 列表
        s2_problems: S2 识别的结构化问题名称列表
        custom_entities: fast_knowledge_match 提取的自定义实体
        child_profile: 儿童档案（可选）
        embedding_helper: EmbeddingHelper 实例（可选，用于 Chroma embedding）

    Returns:
        KnowledgeBundle — 不可变，后续 Section 节点只消费不搜索
    """
    t0 = time.monotonic()
    config = get_bundle_config()

    # ── Step 1a: Neo4j 增强查询 ──
    neo4j_result = None
    entity_seeds: list[str] = []
    if config.bundle_phase1_enabled:
        from src.core.knowledge_qa.neo4j.enhanced_query import query_neo4j_enhanced

        neo4j_result = await query_neo4j_enhanced(
            question=question,
            matched_book_ids=matched_book_ids,
            s2_problems=s2_problems,
            custom_entities=custom_entities,
            embedding_helper=embedding_helper,
        )
        entity_seeds = neo4j_result.entity_seeds
    else:
        from src.core.knowledge_qa.neo4j.enhanced_query import EnhancedNeo4jResult
        neo4j_result = EnhancedNeo4jResult(
            entities={}, relations=[],
            cross_book_conflicts=[], cross_book_consensus=[],
            entity_seeds=[], source_para_ids={},
        )

    # ── Step 1b: Chroma 批量搜索 (并行) ──
    passages, book_metas_by_id = await _batch_chroma_search(
        question=question,
        entity_seeds=entity_seeds,
        matched_book_ids=matched_book_ids,
        source_para_ids=neo4j_result.source_para_ids,
    )

    # ── Step 1c: LazyGraphRAG 增强遍历 ──
    knowledge_context = ""
    lazy_graph_hit_count = 0
    if config.bundle_phase1_enabled:
        knowledge_context, lazy_graph_hit_count = await _enhanced_lazy_graph_traversal(
            question=question,
            entity_seeds=entity_seeds,
            matched_book_ids=matched_book_ids,
            custom_entities=custom_entities,
        )

    # ── Step 1d: 组装 Bundle ──
    # 精简 book_ids
    pruned_book_ids, retained_book_ids = _prune_book_ids(
        matched_book_ids, neo4j_result, passages,
    )

    # 构建 book_index (只含保留的书)
    book_index: dict[str, BookMeta] = {
        bid: meta for bid, meta in book_metas_by_id.items()
        if bid in retained_book_ids
    }
    # 对没有 meta 的保留书，创建默认 meta
    for bid in retained_book_ids:
        if bid not in book_index:
            book_index[bid] = BookMeta(
                book_id=bid, title=bid, normalized_title=bid,
            )

    # 过滤 passages (只保留保留书籍的)
    passages = [p for p in passages if p.book_id in retained_book_ids]

    # 去重 + 截断
    passages = _dedup_by_content(passages)[:MAX_PASSAGES_PER_BUNDLE]

    # 构建 passage_index
    passage_index: dict[str, Passage] = {p.id: p for p in passages}

    # 检测 L1/L2 冲突
    priority_conflicts = _detect_priority_conflicts(neo4j_result, passages)

    # 构建 stats
    t1 = time.monotonic()
    total_chars = sum(len(p.content) for p in passages)
    stats = RetrievalStats(
        neo4j_entity_count=sum(len(v) for v in neo4j_result.entities.values()),
        neo4j_relation_count=len(neo4j_result.relations),
        chroma_passage_count=len([p for p in passages if p.source == "chroma"]),
        lazy_graph_hit_count=lazy_graph_hit_count,
        total_passage_chars=total_chars,
        retrieval_duration_ms=int((t1 - t0) * 1000),
        pruned_book_ids=pruned_book_ids,
        seed_source="s2_problems",
    )

    bundle = KnowledgeBundle(
        question=question,
        matched_book_ids=retained_book_ids,
        neo4j_entities=neo4j_result.entities,
        neo4j_relations=neo4j_result.relations,
        cross_book_conflicts=neo4j_result.cross_book_conflicts,
        cross_book_consensus=neo4j_result.cross_book_consensus,
        passages=passages,
        book_index=book_index,
        passage_index=passage_index,
        priority_conflicts=priority_conflicts,
        retrieval_stats=stats,
    )

    logger.info(
        "KnowledgeBundle 构建完成: %d entities, %d passages, "
        "%d books (pruned %d), %dms",
        stats.neo4j_entity_count, len(passages),
        len(retained_book_ids), len(pruned_book_ids),
        stats.retrieval_duration_ms,
    )

    return bundle


# ═══════════════════════════════════════════════════════════════════════════════
# Step 1b: Chroma batch search
# ═══════════════════════════════════════════════════════════════════════════════


async def _batch_chroma_search(
    question: str,
    entity_seeds: list[str],
    matched_book_ids: list[str],
    source_para_ids: dict[str, list[str]],
) -> tuple[list[Passage], dict[str, BookMeta]]:
    """批量 Chroma 搜索——直接调用 RAG service。

    - 用 entity_seeds 构建多元化 queries
    - 并行执行（semaphore 保护）
    - 语义去重 + neo4j_verified 标记
    """
    from src.service.rag_service import rag_service

    # ── Query 构建：原问题 + 实体种子维度 ──
    queries = [question]
    for ent_name in entity_seeds[:8]:
        if ent_name and ent_name not in queries:
            queries.append(ent_name)

    # ── 并行搜索 ──
    all_raw: list[dict] = []
    seen_ids: set[str] = set()

    async def _search_one(query: str) -> list[dict]:
        try:
            result = await rag_service.search_content(
                query=query,
                limit=CHROMA_RESULTS_PER_QUERY,
                book_ids=matched_book_ids if matched_book_ids else None,
            )
            return result.get("results", [])
        except Exception as e:
            logger.warning("Chroma 搜索失败 (query=%s): %s", query[:50], e)
            return []

    # 并行执行（限制并发数）
    semaphore = asyncio.Semaphore(3)

    async def _search_with_limit(query: str) -> list[dict]:
        async with semaphore:
            return await _search_one(query)

    all_query_results = await asyncio.gather(
        *[_search_with_limit(q) for q in queries[:MAX_QUERIES]],
        return_exceptions=True,
    )

    for results in all_query_results:
        if isinstance(results, Exception):
            continue
        for r in results:
            rid = r.get("id") or r.get("chunk_id", "")
            if rid and rid not in seen_ids:
                seen_ids.add(rid)
                all_raw.append(r)

    # ── 转为 Passage 对象 ──
    passages: list[Passage] = []
    book_metas: dict[str, BookMeta] = {}

    # 收集所有 source_para_ids 做扁平集合
    all_source_para_ids: set[str] = set()
    for pids in source_para_ids.values():
        all_source_para_ids.update(pids)

    for r in all_raw:
        bid = r.get("file_hash", "")
        btitle = normalize_book_title(r.get("source_book", ""))
        chapter = r.get("chapter_title", "未知")
        content = r.get("content", "")
        rid = r.get("id") or r.get("chunk_id", "")
        score = r.get("score", 0.0) or 0.0

        passage = Passage(
            id=rid,
            book_id=bid,
            book_title=btitle,
            chapter_title=chapter,
            content=content,
            score=score,
            source="chroma",
            neo4j_verified=rid in all_source_para_ids,
        )
        passages.append(passage)

        # 记录 book_meta
        if bid and bid not in book_metas:
            book_metas[bid] = BookMeta(
                book_id=bid,
                title=btitle,
                normalized_title=btitle,
            )

    # ── 语义去重（简单版：基于内容前缀 + 分数排序）──
    passages = _dedup_simple(passages)

    logger.info(
        "Chroma 批量搜索完成: %d queries → %d raw → %d deduped passages",
        len(queries), len(all_raw), len(passages),
    )
    return passages, book_metas


# ═══════════════════════════════════════════════════════════════════════════════
# Step 1c: LazyGraphRAG enhanced traversal
# ═══════════════════════════════════════════════════════════════════════════════


async def _enhanced_lazy_graph_traversal(
    question: str,
    entity_seeds: list[str],
    matched_book_ids: list[str],
    custom_entities: list[str],
) -> tuple[str, int]:
    """Neo4j 实体增强的 LazyGraphRAG 遍历。

    增强点:
    1. query 被实体名增强: "{question} {entity_seeds}"
    2. 只对 top-3 书做遍历（而非全部候选书）
    3. 包含 Neo4j 实体的社区获得相关性加分

    Returns:
        (knowledge_context, hit_count)
    """
    if not matched_book_ids:
        return "", 0

    try:
        from src.core.knowledge_qa.graph.traversal import (
            TraversalHit, build_knowledge_context, explore_community_tree,
        )
        from src.core.knowledge_qa.tools import _get_http_client
        from src.utils.http_client import HttpGraphAdapter

        # 精简为 top-3 书
        top_book_ids = matched_book_ids[:3]
        community_repo = HttpGraphAdapter(_get_http_client())

        # 增强 query
        enhanced_query = question
        all_seeds = list(entity_seeds[:10]) + list(custom_entities[:5])
        if all_seeds:
            enhanced_query += " " + " ".join(all_seeds)

        all_hits: list[TraversalHit] = []

        for book_id in top_book_ids:
            try:
                roots = await community_repo.get_roots(scope="book", book_id=book_id)
                for root in roots:
                    hits = await explore_community_tree(
                        question=enhanced_query,
                        root_id=root.node_id,
                        community_repo=community_repo,
                        max_tokens=20000,
                        entity_boost_names=set(all_seeds) if all_seeds else None,
                    )
                    all_hits.extend(hits)
            except Exception as e:
                logger.warning(
                    "LazyGraphRAG 遍历失败 (book=%s): %s", book_id[:8], e,
                )
                continue

        if not all_hits:
            return "", 0

        # 去重 + 构建知识上下文
        seen_chunks: set[str] = set()
        deduped: list[TraversalHit] = []
        for hit in all_hits:
            unique = [c for c in hit.chunk_ids if c not in seen_chunks]
            seen_chunks.update(unique)
            if unique:
                deduped.append(TraversalHit(
                    node_id=hit.node_id, label=hit.label,
                    entity_names=hit.entity_names, chunk_ids=unique,
                ))

        if not deduped:
            return "", 0

        context = await build_knowledge_context(
            question=question, hits=deduped,
            chunk_loader=_make_chunk_loader(),
        )

        if context:
            # 嵌入关联实体提示
            entity_names_set: set[str] = set()
            for hit in deduped:
                for name in (hit.entity_names or []):
                    if name.strip():
                        entity_names_set.add(name.strip())
            if entity_names_set:
                context += (
                    "\n\n## 知识图谱关联实体\n"
                    f"以下实体与问题关联: {', '.join(sorted(entity_names_set)[:30])}\n"
                )

        hit_count = len(deduped)
        logger.info(
            "LazyGraphRAG 增强遍历完成: %d 社区命中, %d chars",
            hit_count, len(context or ""),
        )
        return context or "", hit_count

    except asyncio.TimeoutError:
        logger.warning("LazyGraphRAG 遍历超时 (>10s)，降级")
        return "", 0
    except Exception as e:
        logger.warning("LazyGraphRAG 遍历失败: %s", e)
        return "", 0


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


# ═══════════════════════════════════════════════════════════════════════════════
# Step 1d: Assembly helpers
# ═══════════════════════════════════════════════════════════════════════════════


def _prune_book_ids(
    matched_book_ids: list[str],
    neo4j_result: Any,
    passages: list[Passage],
) -> tuple[list[str], list[str]]:
    """精简 book_ids: 剔除命中不足的候选书。

    命中统计: Neo4j 实体数 + Chroma passage 数。
    阈值: 实体命中 ≥ 3 或 passage 命中 ≥ 5 (满足其一即保留)。

    Returns:
        (pruned_book_ids, retained_book_ids)
    """
    # 统计命中
    entity_hits: dict[str, int] = {}
    for ents in neo4j_result.entities.values():
        for e in ents:
            if e.book_id:
                entity_hits[e.book_id] = entity_hits.get(e.book_id, 0) + 1

    passage_hits: dict[str, int] = {}
    for p in passages:
        if p.book_id:
            passage_hits[p.book_id] = passage_hits.get(p.book_id, 0) + 1

    retained: list[str] = []
    pruned: list[str] = []

    for bid in matched_book_ids:
        eh = entity_hits.get(bid, 0)
        ph = passage_hits.get(bid, 0)
        if eh >= BUNDLE_BOOK_MIN_ENTITY_HITS or ph >= BUNDLE_BOOK_MIN_PASSAGE_HITS:
            retained.append(bid)
        else:
            pruned.append(bid)

    if len(retained) == 0 and matched_book_ids:
        # 至少保留第一本书（防止全部被剔除）
        retained = [matched_book_ids[0]]
        if matched_book_ids[0] in pruned:
            pruned.remove(matched_book_ids[0])

    logger.info(
        "book_ids 精简: %d → %d retained, %d pruned",
        len(matched_book_ids), len(retained), len(pruned),
    )
    return pruned, retained


def _detect_priority_conflicts(
    neo4j_result: Any,
    passages: list[Passage],
) -> list[PriorityConflict]:
    """检测 Neo4j (L1) 与 Chroma 原文 (L2) 之间的矛盾。

    简化实现: 检查 Neo4j 中标记为 CONFLICT 的 cross_book 关系
    + 同一实体在多个 passage 中有矛盾描述。

    完整的语义矛盾检测需要 LLM 参与，此处仅做结构层标记。
    """
    # 对于有跨书冲突的实体，查找相关 passages 作为 L2 证据
    conflicts: list[PriorityConflict] = []

    for cc in neo4j_result.cross_book_conflicts:
        entity_name = cc.entity_name
        related_passages = [
            p for p in passages
            if entity_name.lower() in p.content.lower()
        ]
        if related_passages:
            conflicts.append(PriorityConflict(
                entity_name=entity_name,
                l1_position=f"跨书矛盾: {' vs '.join(cc.books)} (关系类型: {cc.neo4j_relation_type})",
                l2_position=related_passages[0].content[:200] + "...",
                l2_passage_id=related_passages[0].id,
            ))

    return conflicts


# ═══════════════════════════════════════════════════════════════════════════════
# Dedup helpers
# ═══════════════════════════════════════════════════════════════════════════════

# 语义去重相似度阈值——SequenceMatcher ratio ≥ 此值视为近似重复
SEMANTIC_DEDUP_THRESHOLD = 0.90
# 短文本长度阈值——低于此长度的 passage 仅做精确去重（避免短文本误判）
_SHORT_PASSAGE_LEN = 50


def _dedup_simple(passages: list[Passage]) -> list[Passage]:
    """精确去重: 基于内容前 80 字符 + score 排序取最高。"""
    seen_hashes: dict[str, tuple[Passage, float]] = {}
    for p in passages:
        content_hash = p.content[:80].strip()
        if not content_hash:
            continue
        existing = seen_hashes.get(content_hash)
        if existing is None or p.score > existing[1]:
            seen_hashes[content_hash] = (p, p.score)
    # 按 score 降序排列
    sorted_passages = sorted(
        [v[0] for v in seen_hashes.values()],
        key=lambda x: x.score, reverse=True,
    )
    return sorted_passages


def _dedup_by_content(passages: list[Passage]) -> list[Passage]:
    """语义去重: 精确前缀去重 + SequenceMatcher 近似去重。

    两阶段:
    1. 精确去重（前 80 字符 hash 相同 → 保留 score 最高的）
    2. 近似去重（SequenceMatcher ratio ≥ 0.90 → 保留 score 最高的）

    用 difflib.SequenceMatcher 替代 cosine embedding:
    - 无需外部 API 调用，零延迟增加
    - 字符级相似度 ≥ 0.90 在段落级文本上等效于 cosine ≥ 0.90
    - 短文本（< 50 字符）仅做精确去重，避免误判
    """
    if not passages:
        return []

    # ── Stage 1: 精确前缀去重 ──
    exact_deduped = _dedup_simple(passages)

    # ── Stage 2: 近似去重 ──
    return _semantic_dedup(exact_deduped)


def _semantic_dedup(passages: list[Passage]) -> list[Passage]:
    """基于 SequenceMatcher 的近似去重。

    passages 已按 score 降序排列，遇到近似重复时保留先出现的（score 更高的）。
    """
    if len(passages) <= 1:
        return passages

    kept: list[Passage] = [passages[0]]
    # 预计算 kept passages 的 content 片段（前 200 字符用于快速筛选）
    kept_prefixes: list[str] = [passages[0].content[:200]]

    for p in passages[1:]:
        content = p.content
        if len(content) < _SHORT_PASSAGE_LEN:
            # 短文本：仅检查精确匹配
            if content not in [k.content for k in kept]:
                kept.append(p)
                kept_prefixes.append(content[:200])
            continue

        is_dup = False
        prefix = content[:200]
        for i, kp in enumerate(kept_prefixes):
            # 快速预筛选：前 200 字符的 SequenceMatcher
            # 如果前 200 字符相似度 < 0.85，全文不可能 ≥ 0.90
            pre_ratio = difflib.SequenceMatcher(None, prefix, kp).ratio()
            if pre_ratio < 0.85:
                continue
            # 全文相似度计算（较慢，但只在预筛选通过时执行）
            full_ratio = difflib.SequenceMatcher(
                None, content, kept[i].content,
            ).ratio()
            if full_ratio >= SEMANTIC_DEDUP_THRESHOLD:
                is_dup = True
                logger.debug(
                    "语义去重: '%s...' ≈ '%s...' (ratio=%.2f), 保留 score=%.3f",
                    content[:40], kept[i].content[:40], full_ratio, kept[i].score,
                )
                break

        if not is_dup:
            kept.append(p)
            kept_prefixes.append(prefix)

    if len(kept) < len(passages):
        logger.info(
            "语义去重: %d → %d passages (移除 %d 近似重复)",
            len(passages), len(kept), len(passages) - len(kept),
        )

    return kept
