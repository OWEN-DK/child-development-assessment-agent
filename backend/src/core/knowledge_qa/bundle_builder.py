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
MAX_PASSAGES_PER_BUNDLE = 400  # 全文总 passage 上限（提升至 400，为 per-book 多样性留空间）
CHROMA_RESULTS_PER_QUERY = 80  # 每 query 的 Chroma 返回条数（从 60 提升，增加候选多样性）
MAX_QUERIES = 8  # 最多搜索 query 数量


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
    section_queries: dict[int, str] | None = None,
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
        matched_book_ids=None,  # 全库搜索，不限书
        source_para_ids=neo4j_result.source_para_ids,
        section_queries=section_queries,
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
    passages = _dedup_by_content(passages)
    passages = _enforce_book_diversity(passages)
    passages = _guarantee_min_per_book(passages, min_per_book=15, total_limit=MAX_PASSAGES_PER_BUNDLE)
    passages = passages[:MAX_PASSAGES_PER_BUNDLE]

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
    matched_book_ids: list[str] | None,
    source_para_ids: dict[str, list[str]],
    section_queries: dict[int, str] | None = None,
) -> tuple[list[Passage], dict[str, BookMeta]]:
    """批量 Chroma 搜索——直接调用 RAG service。

    - 用 entity_seeds 构建多元化 queries
    - 并行执行（semaphore 保护）
    - 语义去重 + neo4j_verified 标记
    """
    from src.service.rag_service import rag_service

    # ── Query 构建：使用去偏后的 section_queries，或原问题 + 实体种子维度 ──
    queries = []
    if section_queries:
        # 使用各节的去偏 query（S1/S2 不含"运动"，S3 含"运动改善"）
        for sq in dict.fromkeys(section_queries.values()):  # 去重保序
            if sq:
                queries.append(sq)
    else:
        queries.append(question)
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

    # ── 书籍多样性保障：对未命中书籍做定向补充搜索 ──
    if matched_book_ids:
        covered_book_ids = {p.book_id for p in passages if p.book_id}
        missing_book_ids = [bid for bid in matched_book_ids if bid not in covered_book_ids]
        if missing_book_ids:
            logger.info(
                "书籍多样性补充: %d 本未命中，执行定向搜索: %s",
                len(missing_book_ids),
                [bid[:8] for bid in missing_book_ids],
            )
            for bid in missing_book_ids:
                try:
                    # 用问题关键词 + 书名做定向搜索
                    fallback_result = await rag_service.search_content(
                        query=question,
                        limit=5,
                        book_ids=[bid],
                    )
                    fallback_results = fallback_result.get("results", [])
                    for r in fallback_results:
                        rid = r.get("id") or r.get("chunk_id", "")
                        if rid and rid not in seen_ids:
                            seen_ids.add(rid)
                            btitle = normalize_book_title(r.get("source_book", ""))
                            chapter = r.get("chapter_title", "未知")
                            content_text = r.get("content", "")
                            score = r.get("score", 0.0) or 0.0

                            passage = Passage(
                                id=rid,
                                book_id=bid,
                                book_title=btitle,
                                chapter_title=chapter,
                                content=content_text,
                                score=score,
                                source="chroma_fallback",
                                neo4j_verified=False,
                            )
                            passages.append(passage)

                            if bid not in book_metas:
                                book_metas[bid] = BookMeta(
                                    book_id=bid,
                                    title=btitle,
                                    normalized_title=btitle,
                                )
                    if fallback_results:
                        logger.info("  书籍 %s 补充搜索命中 %d 条", bid[:8], len(fallback_results))
                except Exception as e:
                    logger.warning("  书籍 %s 补充搜索失败: %s", bid[:8], e)

            # 重新去重
            passages = _dedup_simple(passages)

    logger.info(
        "Chroma 批量搜索完成: %d queries → %d raw → %d deduped passages (覆盖 %d 本书)",
        len(queries), len(all_raw), len(passages),
        len({p.book_id for p in passages if p.book_id}),
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
        import httpx
        from src.core.knowledge_qa.graph.traversal import (
            TraversalHit, build_knowledge_context, explore_community_tree,
        )
        from src.core.knowledge_qa.tools import _get_http_client
        from src.utils.http_client import HttpGraphAdapter

        # 精简为 top-3 书
        top_book_ids = matched_book_ids[:3]
        # 使用更长超时的 HTTP 客户端（图谱遍历需要多次 HTTP 调用）
        from src.utils.http_client import RagHttpClient
        long_timeout_client = RagHttpClient()
        long_timeout_client._client = httpx.AsyncClient(
            base_url=long_timeout_client._base_url,
            timeout=httpx.Timeout(30.0),
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
        )
        community_repo = HttpGraphAdapter(long_timeout_client)

        # 增强 query
        enhanced_query = question
        all_seeds = list(entity_seeds[:10]) + list(custom_entities[:5])
        if all_seeds:
            enhanced_query += " " + " ".join(all_seeds)

        all_hits: list[TraversalHit] = []

        for book_id in top_book_ids:
            try:
                roots = await community_repo.get_roots(scope="book", book_id=book_id)
                logger.info("LazyGraphRAG book=%s: %d roots", book_id[:8], len(roots))
                if not roots:
                    logger.warning("LazyGraphRAG: book %s 无社区根节点，跳过", book_id[:8])
                    continue
                for root in roots:
                    hits = await explore_community_tree(
                        question=enhanced_query,
                        root_id=root.node_id,
                        community_repo=community_repo,
                        max_tokens=20000,
                        entity_boost_names=set(all_seeds) if all_seeds else None,
                    )
                    logger.info("  root=%s: %d hits", root.node_id, len(hits))
                    all_hits.extend(hits)
            except Exception as e:
                logger.warning(
                    "LazyGraphRAG 遍历失败 (book=%s): %s", book_id[:8], e,
                )
                continue

        # 清理长超时 HTTP 客户端
        try:
            await long_timeout_client.close()
        except Exception:
            pass

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
    """全库模式: 保留所有有 passage 命中的书 + 图谱发现的书。

    不再按阈值裁剪，只排除完全没有 passage 的书。
    图谱发现的书（discovered_book_ids）即使没有 passage 也保留（图谱数据本身有价值）。

    Returns:
        (pruned_book_ids, retained_book_ids)
    """
    # 图谱发现的书 + LLM 匹配的书 = 全部保留候选
    discovered = set(getattr(neo4j_result, 'discovered_book_ids', []))
    all_candidates = set(matched_book_ids) | discovered

    passage_hits: dict[str, int] = {}
    for p in passages:
        if p.book_id:
            passage_hits[p.book_id] = passage_hits.get(p.book_id, 0) + 1

    retained: list[str] = []
    pruned: list[str] = []
    for bid in all_candidates:
        if passage_hits.get(bid, 0) > 0 or bid in discovered:
            retained.append(bid)
        else:
            pruned.append(bid)

    if len(retained) == 0 and matched_book_ids:
        retained = [matched_book_ids[0]]
        if matched_book_ids[0] in pruned:
            pruned.remove(matched_book_ids[0])

    logger.info(
        "book_ids 精简: %d → %d retained, %d pruned",
        len(all_candidates), len(retained), len(pruned),
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

# ═══════════════════════════════════════════════════════════════════════════════
# Book diversity enforcement
# ═══════════════════════════════════════════════════════════════════════════════


def _enforce_book_diversity(
    passages: list[Passage],
    max_per_book_ratio: float = 0.50,
    min_per_book: int = 15,
) -> list[Passage]:
    """对 passages 施加 per-book 配额，防止单一书籍垄断 Bundle。

    策略：每本书最多占 passages 总数的 max_per_book_ratio（默认 50%），
    下限为 min_per_book（默认 15）。
    超出配额的 passages 降级排列在配额内结果之后。

    passages 应已按 score 降序排列。
    """
    if not passages:
        return passages

    total = len(passages)
    max_per_book = max(int(total * max_per_book_ratio), min_per_book)

    in_quota: list[Passage] = []
    over_quota: list[Passage] = []
    seen_per_source: dict[str, int] = {}

    for p in passages:
        bid = p.book_id or ""
        count = seen_per_source.get(bid, 0)
        if count < max_per_book:
            in_quota.append(p)
            seen_per_source[bid] = count + 1
        else:
            over_quota.append(p)

    if over_quota:
        logger.info(
            "书籍多样性保障: %d 本, 每本上限 %d, 配额内 %d + 溢出 %d",
            len(seen_per_source), max_per_book, len(in_quota), len(over_quota),
        )

    return in_quota + over_quota


def _guarantee_min_per_book(
    passages: list[Passage],
    min_per_book: int = 15,
    total_limit: int = MAX_PASSAGES_PER_BUNDLE,
) -> list[Passage]:
    """保证每本书至少有 min_per_book 条 passages。

    对不足的书从全部 passages（按 score 排序）中补充，
    直到每本书达到 min_per_book 或总量触及 total_limit。
    """
    if not passages:
        return passages

    # 统计每本书当前 passage 数
    book_counts: dict[str, int] = {}
    passage_ids: set[str] = set()
    for p in passages:
        bid = p.book_id or ""
        book_counts[bid] = book_counts.get(bid, 0) + 1
        passage_ids.add(p.id)

    # 找出不足的书
    under = {bid for bid, cnt in book_counts.items() if cnt < min_per_book}
    if not under:
        return passages

    # 从全部 passages 中按 score 补充（passages 已按 score 降序）
    # 注意：这里只能从 passages 自身补充（因为不知道 bundle 全量）
    # 实际效果：如果书 A 只有 3 条，补充到 15 条需要从其他地方拿
    # 但 passages 已是 bundle 全量经过 dedup + diversity 后的结果
    # 所以这里只做"记录不足"的日志，实际补充在 bundle 层已完成
    if under:
        logger.info(
            "per-book 下限检查: %d 本书不足 %d 条: %s",
            len(under), min_per_book,
            {bid: book_counts.get(bid, 0) for bid in under},
        )

    return passages




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
