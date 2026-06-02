"""Phase 5a v3: 图感知跨书分析 — 社区级匹配 + 批量 LLM 精判。

核心改进:
1. 社区级匹配 — 用图的社区结构缩小搜索空间（O(C1×C2) 而非 O(N×M)）
2. 批量 LLM — 一次 API 调用判断多个候选对，成本降低 10-50x
3. 嵌入式实体上下文 — 实体描述 + 邻居关系一起编码，比纯名称更准

设计文档: docs/architecture/13-跨书知识融合方案-v2.md §5
"""

from __future__ import annotations

import json
import asyncio
import logging
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol
from neo4j import NotificationClassification

from .schema import (
    CROSS_BOOK_RELATION_TYPES,
    CROSS_RELATION_TYPE_COMBOS,
    VALID_CROSS_RELATION_COMBOS,
)

logger = logging.getLogger(__name__)


# ── Protocol ─────────────────────────────────────────────────


class EmbeddingHelper(Protocol):
    async def embed_text(self, text: str) -> list[float] | None: ...
    async def embed_batch(self, texts: list[str]) -> list[list[float]]: ...
    def cosine_similarity(self, a: list[float], b: list[float]) -> float: ...


class LLMClient(Protocol):
    async def generate(self, prompt: str, model: str) -> str: ...


# ── 数据结构 ─────────────────────────────────────────────────


@dataclass
class EntityCandidate:
    name: str
    entity_type: str
    description: str
    book_id: str
    embedding: list[float] = field(default_factory=list)
    neighborhood: str = ""  # 邻居实体摘要


@dataclass
class CommunityInfo:
    community_id: str
    book_id: str
    entity_names: list[str] = field(default_factory=list)
    entity_types: list[str] = field(default_factory=list)
    description: str = ""
    embedding: list[float] = field(default_factory=list)


@dataclass
class EntityMatchCandidate:
    index: int
    new_entity: str
    new_type: str
    new_desc: str
    new_book_id: str  # 新实体所属的 book_id（修复 BUG-1）
    matched_entity: str
    matched_type: str
    matched_desc: str
    matched_book_id: str
    matched_book_title: str
    similarity: float
    llm_same: bool | None = None
    llm_reason: str = ""
    reviewer_decision: str = "skip"


@dataclass
class CrossRelationCandidate:
    index: int
    source_entity: str
    source_type: str
    source_book: str
    target_entity: str
    target_type: str
    target_book: str
    relation_type: str
    confidence: float
    reason: str
    evidence_summary: str = ""
    reviewer_decision: str = "skip"


@dataclass
class CrossBookAnalysisResult:
    book_id: str
    generated_at: str
    source_books: list[dict] = field(default_factory=list)
    entity_matches: list[EntityMatchCandidate] = field(default_factory=list)
    cross_relations: list[CrossRelationCandidate] = field(default_factory=list)
    total_new_entities: int = 0
    total_other_entities: int = 0
    match_candidates_count: int = 0
    relation_candidates_count: int = 0


# ── 核心引擎 ─────────────────────────────────────────────────


class CrossBookPhase5a:
    """Phase 5a v3: 图感知跨书分析引擎。

    三层漏斗:
    1. 社区级匹配 — embedding 比较社区描述，找到主题重叠的社区对
    2. 实体级粗筛 — 在匹配社区内，embedding 比较实体对
    3. 批量 LLM 精判 — 一次 API 判断 5-10 个候选对
    """

    def __init__(
        self,
        neo4j_driver,
        embedding_helper: EmbeddingHelper | None = None,
        llm_client: LLMClient | None = None,
        entity_similarity_threshold: float = 0.85,
        cross_relation_threshold: float = 0.45,
    ):
        self._neo4j = neo4j_driver
        self._emb = embedding_helper
        self._llm = llm_client
        self._entity_sim_th = entity_similarity_threshold
        self._cross_rel_th = cross_relation_threshold

    async def run_phase5a(
        self,
        book_id: str,
        output_dir: str | None = None,
    ) -> CrossBookAnalysisResult:
        start = time.monotonic()
        result = CrossBookAnalysisResult(
            book_id=book_id,
            generated_at=time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        )

        try:
            # ── Step 1: 加载图结构 ──
            logger.info("Phase 5a: 加载图结构...")
            new_entities = await self._load_book_entities(book_id)
            result.total_new_entities = len(new_entities)
            logger.info("Phase 5a: 新书实体 %d 个", len(new_entities))

            if not new_entities:
                logger.info("新书 %s 无实体，跳过", book_id)
                return result

            other_entities = await self._load_other_entities(book_id)
            result.total_other_entities = len(other_entities)
            logger.info("Phase 5a: 其他书实体 %d 个", len(other_entities))

            if not other_entities:
                logger.info("Neo4j 中无其他书实体，跳过")
                return result

            # 加载社区结构
            new_communities = await self._load_communities(book_id)
            other_communities = await self._load_other_communities(book_id)
            logger.info("Phase 5a: 新书 %d 社区, 其他书 %d 社区",
                        len(new_communities), len(other_communities))

            # 加载邻居上下文
            await self._load_neighborhoods(new_entities + other_entities)

            # ── Step 2: 批量 Embedding ──
            logger.info("Phase 5a: 批量 Embedding...")
            all_entities = new_entities + other_entities
            await self._batch_embed_entities(all_entities)
            await self._batch_embed_communities(new_communities + other_communities)
            logger.info("Phase 5a: Embedding 完成")

            # ── Step 3: 社区级匹配 → 确定哪些社区对需要深入分析 ──
            matched_community_pairs = self._match_communities(
                new_communities, other_communities,
            )
            logger.info("Phase 5a: 匹配到 %d 个社区对", len(matched_community_pairs))

            # ── Step 4: 在匹配社区内做实体消歧 ──
            entity_pairs_to_judge = []
            if matched_community_pairs:
                entity_pairs_to_judge = self._find_entity_matches_in_communities(
                    new_entities, other_entities,
                    matched_community_pairs,
                )
            else:
                # 无社区信息时 fallback 到全局比较
                entity_pairs_to_judge = self._find_entity_matches_global(
                    new_entities, other_entities,
                )
            logger.info("Phase 5a: 实体消歧候选 %d 对", len(entity_pairs_to_judge))

            # 批量 LLM 精判实体消歧
            if entity_pairs_to_judge and self._llm:
                entity_matches = await self._batch_judge_entity_matches(
                    entity_pairs_to_judge,
                )
                result.entity_matches = entity_matches
                result.match_candidates_count = len(entity_matches)
                logger.info("Phase 5a: 实体消歧确认 %d 个", len(entity_matches))

            # ── Step 5: 跨书语义关系发现 ──
            cross_pairs = self._find_cross_relation_candidates(
                new_entities, other_entities,
                matched_community_pairs,
                entity_match_pairs=entity_pairs_to_judge or None,
            )
            logger.info("Phase 5a: 跨书关系候选 %d 对", len(cross_pairs))

            if cross_pairs and self._llm:
                cross_relations = await self._batch_judge_cross_relations(
                    cross_pairs,
                )
                result.cross_relations = cross_relations
                result.relation_candidates_count = len(cross_relations)
                logger.info("Phase 5a: 跨书关系确认 %d 个", len(cross_relations))

            # ── Step 6: 持久化 ──
            result.source_books = await self._get_source_books(book_id)
            if output_dir:
                self._save_to_json(result, output_dir)
            self._save_to_redis(result)

            duration_ms = int((time.monotonic() - start) * 1000)
            logger.info(
                "Phase 5a 完成: 消歧=%d, 关系=%d, 耗时=%dms",
                len(result.entity_matches), len(result.cross_relations), duration_ms,
            )

        except Exception as e:
            logger.error("Phase 5a 执行失败: %s", e, exc_info=True)
            raise

        except asyncio.CancelledError:
            logger.info("Phase 5a: 任务被取消")
            raise

        return result

    # ── 图结构加载 ───────────────────────────────────────────

    async def _load_book_entities(self, book_id: str) -> list[EntityCandidate]:
        query = """
        MATCH (n)
        WHERE $book_id IN coalesce(n.book_ids, [n.book_id])
          AND NOT n:Book
          AND NOT any(l IN labels(n) WHERE l IN ['MergeLog', 'D2G_Staging'])
        RETURN n.name AS name, labels(n)[0] AS entity_type,
               n.description AS description, n.book_id AS book_id,
               coalesce(n.embedding, []) AS embedding
        """
        async with self._neo4j.session() as session:
            result = await session.run(query, book_id=book_id)
            records = await result.data()
        return [EntityCandidate(
            name=r["name"], entity_type=r["entity_type"],
            description=r.get("description", ""), book_id=r["book_id"],
            embedding=r.get("embedding") or [],
        ) for r in records]

    async def _load_other_entities(self, book_id: str) -> list[EntityCandidate]:
        query = """
        MATCH (n)
        WHERE NOT $book_id IN coalesce(n.book_ids, [n.book_id])
          AND NOT n:Book
          AND NOT any(l IN labels(n) WHERE l IN ['MergeLog', 'D2G_Staging'])
        RETURN n.name AS name, labels(n)[0] AS entity_type,
               n.description AS description, n.book_id AS book_id,
               coalesce(n.embedding, []) AS embedding
        """
        async with self._neo4j.session() as session:
            result = await session.run(query, book_id=book_id)
            records = await result.data()
        return [EntityCandidate(
            name=r["name"], entity_type=r["entity_type"],
            description=r.get("description", ""), book_id=r["book_id"],
            embedding=r.get("embedding") or [],
        ) for r in records]

    async def _load_communities(self, book_id: str) -> list[CommunityInfo]:
        """加载社区结构。优先读 AutoCommunity，不存在时用图结构聚类。"""
        # 尝试读取 AutoCommunity
        try:
            query = """
            MATCH (c:AutoCommunity)-[:CONTAINS]->(n)
            WHERE $book_id IN coalesce(n.book_ids, [n.book_id])
              OR c.book_id = $book_id
            RETURN c.name AS community_id, c.description AS description,
                   collect(n.name) AS entity_names,
                   collect(labels(n)[0]) AS entity_types
            """
            async with self._neo4j.session(notifications_disabled_classifications=[NotificationClassification.UNRECOGNIZED]) as session:
                result = await session.run(query, book_id=book_id)
                records = await result.data()
            if records:
                return [CommunityInfo(
                    community_id=r["community_id"],
                    book_id=book_id,
                    entity_names=r.get("entity_names", []),
                    entity_types=r.get("entity_types", []),
                    description=r.get("description", ""),
                ) for r in records]
        except Exception:
            pass
        # AutoCommunity 不存在，用图结构聚类作为虚拟社区
        return await self._build_structural_communities(book_id)

    async def _load_other_communities(self, book_id: str) -> list[CommunityInfo]:
        """加载其他书籍的社区结构。"""
        try:
            query = """
            MATCH (c:AutoCommunity)-[:CONTAINS]->(n)
            WHERE c.book_id <> $book_id
            RETURN c.name AS community_id, c.book_id AS book_id,
                   c.description AS description,
                   collect(n.name) AS entity_names,
                   collect(labels(n)[0]) AS entity_types
            """
            async with self._neo4j.session(notifications_disabled_classifications=[NotificationClassification.UNRECOGNIZED]) as session:
                result = await session.run(query, book_id=book_id)
                records = await result.data()
            if records:
                return [CommunityInfo(
                    community_id=r["community_id"],
                    book_id=r.get("book_id", ""),
                    entity_names=r.get("entity_names", []),
                    entity_types=r.get("entity_types", []),
                    description=r.get("description", ""),
                ) for r in records]
        except Exception:
            pass
        # 获取所有其他书籍的 book_id，逐本构建结构社区
        other_book_ids = await self._get_other_book_ids(book_id)
        communities = []
        for oid in other_book_ids:
            communities.extend(await self._build_structural_communities(oid))
        return communities

    async def _get_other_book_ids(self, book_id: str) -> list[str]:
        """获取其他书籍的 ID 列表。"""
        query = """
        MATCH (n)
        WHERE NOT $book_id IN coalesce(n.book_ids, [n.book_id])
          AND NOT n:Book
          RETURN DISTINCT n.book_id AS book_id
        """
        try:
            async with self._neo4j.session() as session:
                result = await session.run(query, book_id=book_id)
                records = await result.data()
            return [r["book_id"] for r in records if r.get("book_id")]
        except Exception:
            return []

    async def _build_structural_communities(self, book_id: str) -> list[CommunityInfo]:
        """基于 Neo4j 图结构做 Louvain 社区检测，结果缓存到 Neo4j。

        流程:
        1. 从 Neo4j 加载实体 + 关系 → 构建 networkx 图
        2. Louvain 社区检测
        3. 社区结果写入 Neo4j（AutoCommunity 节点 + CONTAINS 边）
        4. 返回 CommunityInfo 列表
        """
        # Step 1: 从 Neo4j 加载图结构
        query = """
        MATCH (n)
        WHERE $book_id IN coalesce(n.book_ids, [n.book_id])
          AND NOT n:Book
          AND NOT any(l IN labels(n) WHERE l IN ['MergeLog', 'D2G_Staging'])
        OPTIONAL MATCH (n)-[r]-(m)
        WHERE NOT m:Book
          AND NOT any(l IN labels(m) WHERE l IN ['MergeLog', 'D2G_Staging'])
          AND $book_id IN coalesce(m.book_ids, [m.book_id])
        RETURN n.name AS name, labels(n)[0] AS entity_type,
               n.description AS description,
               collect(DISTINCT {name: m.name, type: labels(m)[0]}) AS neighbors
        """
        try:
            async with self._neo4j.session() as session:
                result = await session.run(query, book_id=book_id)
                records = await result.data()
        except Exception as e:
            logger.warning("加载图结构失败: %s", e)
            return []

        if not records:
            return []

        # Step 2: 构建 networkx 图
        try:
            import networkx as nx
            import asyncio
            import community as community_louvain
        except ImportError as e:
            logger.warning("缺少依赖 (networkx/community-louvain): %s", e)
            return await self._fallback_structural_communities(records, book_id)

        G = nx.Graph()
        entity_info: dict[str, dict] = {}
        for r in records:
            name = r["name"]
            # 过滤非字符串节点名（Louvain 要求所有节点名必须为字符串）
            if not isinstance(name, str) or not name.strip():
                continue
            G.add_node(name)
            entity_info[name] = {
                "entity_type": r.get("entity_type", ""),
                "description": r.get("description", ""),
            }
            for nb in r.get("neighbors", []):
                nb_name = nb.get("name", "")
                if not isinstance(nb_name, str) or not nb_name.strip():
                    continue
                if nb_name != name:
                    G.add_node(nb_name)
                    G.add_edge(name, nb_name)

        if G.number_of_nodes() < 3:
            logger.info("节点数 %d < 3，跳过社区检测", G.number_of_nodes())
            return []

        # Step 3: Louvain 社区检测（CPU 密集，放线程池）
        try:
            partition = await asyncio.to_thread(
                community_louvain.best_partition, G, random_state=42,
            )
        except Exception as e:
            logger.warning("Louvain 社区检测失败: %s", e)
            return await self._fallback_structural_communities(records, book_id)

        # Step 4: 按社区分组
        communities_by_id: dict[int, list[str]] = {}
        for name, comm_id in partition.items():
            communities_by_id.setdefault(comm_id, []).append(name)

        # Step 5: 写入 Neo4j（AutoCommunity 节点 + CONTAINS 边）
        try:
            async with self._neo4j.session() as session:
                # 先清理该书旧的 AutoCommunity
                await session.run("""
                    MATCH (c:AutoCommunity {book_id: $book_id})
                    DETACH DELETE c
                """, book_id=book_id)

                for comm_id, members in communities_by_id.items():
                    if len(members) < 2:
                        continue
                    # 生成社区描述
                    types = list(set(
                        entity_info.get(m, {}).get("entity_type", "")
                        for m in members
                    ))
                    label = " + ".join(members[:3])
                    if len(members) > 3:
                        label += f" +{len(members)-3} more"

                    await session.run("""
                        CREATE (c:AutoCommunity {
                            community_id: $comm_id,
                            book_id: $book_id,
                            name: $label,
                            description: $description,
                            entity_count: $count
                        })
                    """, comm_id=str(comm_id), book_id=book_id,
                        label=label, description=", ".join(types),
                        count=len(members))

                    # 建立 CONTAINS 边
                    for member_name in members:
                        await session.run("""
                            MATCH (c:AutoCommunity {community_id: $comm_id, book_id: $book_id})
                            MATCH (n) WHERE n.name = $name
                              AND $book_id IN coalesce(n.book_ids, [n.book_id])
                            MERGE (c)-[:CONTAINS]->(n)
                        """, comm_id=str(comm_id), book_id=book_id,
                            name=member_name)

            logger.info("社区已持久化到 Neo4j: %d 个社区, %d 个实体",
                         len([c for c in communities_by_id.values() if len(c) >= 2]),
                         G.number_of_nodes())
        except Exception as e:
            logger.warning("社区持久化到 Neo4j 失败: %s", e)

        # Step 6: 返回 CommunityInfo
        communities = []
        for comm_id, members in communities_by_id.items():
            if len(members) < 2:
                continue
            types = [entity_info.get(m, {}).get("entity_type", "") for m in members]
            descs = [entity_info.get(m, {}).get("description", "") for m in members]
            desc_parts = list(set(types))
            for d in descs[:3]:
                if d:
                    desc_parts.append(d[:80])
            communities.append(CommunityInfo(
                community_id=f"louvain_{book_id}_{comm_id}",
                book_id=book_id,
                entity_names=members,
                entity_types=types,
                description=" | ".join(desc_parts),
            ))

        return communities

    async def _fallback_structural_communities(
        self, records: list[dict], book_id: str,
    ) -> list[CommunityInfo]:
        """Louvain 不可用时的 fallback：共享邻居聚类。"""
        entity_neighbors: dict[str, set[str]] = {}
        entity_types: dict[str, str] = {}
        entity_descs: dict[str, str] = {}
        for r in records:
            name = r["name"]
            entity_neighbors[name] = set(
                nb.get("name", "") for nb in r.get("neighbors", []) if nb.get("name")
            )
            entity_types[name] = r.get("entity_type", "")
            entity_descs[name] = r.get("description", "")

        parent = {name: name for name in entity_neighbors}

        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(x, y):
            rx, ry = find(x), find(y)
            if rx != ry:
                parent[rx] = ry

        names = list(entity_neighbors.keys())
        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                shared = entity_neighbors[names[i]] & entity_neighbors[names[j]]
                if len(shared) >= 3:
                    union(names[i], names[j])

        clusters: dict[str, list[str]] = {}
        for name in names:
            root = find(name)
            clusters.setdefault(root, []).append(name)

        communities = []
        for cluster_id, (root, members) in enumerate(clusters.items()):
            if len(members) < 2:
                continue
            types = [entity_types.get(m, "") for m in members]
            descs = [entity_descs.get(m, "") for m in members]
            desc_parts = list(set(types))
            for d in descs[:3]:
                if d:
                    desc_parts.append(d[:80])
            communities.append(CommunityInfo(
                community_id=f"fallback_{book_id}_{cluster_id}",
                book_id=book_id,
                entity_names=members,
                entity_types=types,
                description=" | ".join(desc_parts),
            ))

        logger.info("Fallback 社区: %d 个实体 → %d 个社区", len(names), len(communities))
        return communities

    async def _load_neighborhoods(self, entities: list[EntityCandidate]) -> None:
        """加载实体的邻居上下文（关系 + 邻居名称）。"""
        names = [e.name for e in entities]
        if not names:
            return
        query = """
        UNWIND $names AS name
        MATCH (n {name: name})-[r]-(m)
        RETURN name AS source,
               collect(DISTINCT m.name + '(' + labels(m)[0] + ')')[..5] AS neighbors
        """
        try:
            async with self._neo4j.session() as session:
                result = await session.run(query, names=names)
                records = await result.data()
            neighbor_map = {r["source"]: ", ".join(r.get("neighbors", [])) for r in records}
            for e in entities:
                e.neighborhood = neighbor_map.get(e.name, "")
        except Exception as e:
            logger.warning("加载邻居上下文失败: %s", e)

    # ── Embedding ────────────────────────────────────────────

    async def _batch_embed_entities(self, entities: list[EntityCandidate]) -> None:
        """批量计算实体的 embedding 向量。

        优化（修复 BUG-3）：
        1. 已有 embedding 的实体跳过（从 Neo4j 读取的）
        2. 新计算的 embedding 写回 Neo4j 持久化
        3. 并发 API 调用（semaphore 控流），避免串行等待
        """
        if not self._emb or not entities:
            return

        # 分离：已有 embedding 的跳过，只 embed 缺失的
        need_embed = [e for e in entities if not e.embedding]
        cached_count = len(entities) - len(need_embed)
        if cached_count > 0:
            logger.info(
                "Phase 5a embedding: %d/%d 实体已有缓存，需计算 %d 个",
                cached_count, len(entities), len(need_embed),
            )
        if not need_embed:
            return

        # 构建 embedding 文本
        texts = []
        for e in need_embed:
            ctx = f"{e.name}: {e.description}"
            if e.neighborhood:
                ctx += f" [邻居: {e.neighborhood}]"
            texts.append(ctx)

        batch_size = 50
        # 并发控制：最多 CONCURRENT_EMBED_BATCHES 个 API 调用同时进行
        import asyncio
        import os
        max_concurrent = int(os.environ.get("PHASE5A_EMBED_CONCURRENCY", "3"))
        sem = asyncio.Semaphore(max_concurrent)

        async def embed_one_batch(batch_texts, batch_entities):
            async with sem:
                try:
                    embeddings = await self._emb.embed_batch(batch_texts)
                    for entity, emb in zip(batch_entities, embeddings):
                        if emb:
                            entity.embedding = emb
                except Exception as ex:
                    logger.warning(
                        "Entity embedding batch 失败 %d 条: %s", len(batch_texts), ex,
                    )
                    # batch 失败 → 逐条 fallback
                    for entity, text in zip(batch_entities, batch_texts):
                        try:
                            emb = await self._emb.embed_text(text)
                            if emb:
                                entity.embedding = emb
                        except Exception:
                            pass

        # 并发执行所有 batch
        tasks = []
        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i:i + batch_size]
            batch_entities = need_embed[i:i + batch_size]
            tasks.append(embed_one_batch(batch_texts, batch_entities))

        if tasks:
            async with asyncio.TaskGroup() as tg:
                _embed_tg_tasks = [tg.create_task(t) for t in tasks]

        # 将新计算的 embedding 持久化回 Neo4j
        embed_success = [e for e in need_embed if e.embedding]
        if embed_success:
            await self._persist_embeddings_to_neo4j(embed_success)
            logger.info(
                "Phase 5a embedding: 已计算并持久化 %d 个实体",
                len(embed_success),
            )

    async def _persist_embeddings_to_neo4j(
        self, entities: list[EntityCandidate],
    ) -> None:
        """将 entity embedding 写回 Neo4j 实体节点的 embedding 属性。

        持久化后，下次 Phase 5a 调用时可直接从 Neo4j 读取已有 embedding，
        避免重复计算（修复 BUG-3）。
        """
        if not entities:
            return
        try:
            async with self._neo4j.session() as session:
                await session.run(
                    """
                    UNWIND $items AS item
                    MATCH (n {name: item.name})
                    WHERE item.book_id IN coalesce(n.book_ids, [n.book_id])
                    SET n.embedding = item.embedding
                    """,
                    items=[
                        {"name": e.name, "book_id": e.book_id, "embedding": e.embedding}
                        for e in entities
                    ],
                )
        except Exception as e:
            logger.warning("Embedding 持久化到 Neo4j 失败: %s", e)

    async def _batch_embed_communities(self, communities: list[CommunityInfo]) -> None:
        if not self._emb or not communities:
            return
        texts = []
        for c in communities:
            desc = c.description or ", ".join(set(c.entity_types)) or ", ".join(c.entity_names[:5])
            texts.append(desc)

        batch_size = 20
        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i:i + batch_size]
            batch_comms = communities[i:i + batch_size]
            try:
                embeddings = await self._emb.embed_batch(batch_texts)
                for comm, emb in zip(batch_comms, embeddings):
                    if emb:
                        comm.embedding = emb
            except Exception as ex:
                logger.warning("Community embedding 失败: %s", ex)

    # ── 社区级匹配 ───────────────────────────────────────────

    def _match_communities(
        self,
        new_comms: list[CommunityInfo],
        other_comms: list[CommunityInfo],
        threshold: float = 0.5,
    ) -> list[tuple[CommunityInfo, CommunityInfo, float]]:
        """匹配新书社区与已有书社区。返回 (new_comm, other_comm, similarity) 列表。"""
        pairs = []
        for nc in new_comms:
            if not nc.embedding:
                continue
            for oc in other_comms:
                if not oc.embedding:
                    continue
                sim = self._emb.cosine_similarity(nc.embedding, oc.embedding)
                if sim >= threshold:
                    pairs.append((nc, oc, sim))
        # 按相似度降序
        pairs.sort(key=lambda x: x[2], reverse=True)
        return pairs

    # ── 实体级候选选择 ───────────────────────────────────────

    def _find_entity_matches_in_communities(
        self,
        new_entities: list[EntityCandidate],
        other_entities: list[EntityCandidate],
        matched_pairs: list[tuple[CommunityInfo, CommunityInfo, float]],
    ) -> list[tuple[EntityCandidate, EntityCandidate, float]]:
        """在匹配的社区对内找实体消歧候选。"""
        # 构建社区→实体映射
        new_comm_entities: dict[str, set[str]] = {}
        other_comm_entities: dict[str, set[str]] = {}
        for nc, oc, _ in matched_pairs:
            new_comm_entities.setdefault(nc.community_id, set(nc.entity_names))
            other_comm_entities.setdefault(oc.community_id, set(oc.entity_names))

        entity_by_name = {e.name: e for e in new_entities + other_entities}

        candidates = []
        seen = set()

        for nc, oc, comm_sim in matched_pairs:
            new_names = new_comm_entities.get(nc.community_id, set())
            other_names = other_comm_entities.get(oc.community_id, set())

            for nn in new_names:
                ne = entity_by_name.get(nn)
                if not ne or not ne.embedding:
                    continue
                for on in other_names:
                    oe = entity_by_name.get(on)
                    if not oe or not oe.embedding:
                        continue
                    if ne.entity_type != oe.entity_type:
                        continue  # 消歧只看同类型
                    key = (nn, on)
                    if key in seen:
                        continue
                    seen.add(key)
                    sim = self._emb.cosine_similarity(ne.embedding, oe.embedding)
                    if sim >= self._entity_sim_th:
                        candidates.append((ne, oe, sim))

        return candidates

    def _find_entity_matches_global(
        self,
        new_entities: list[EntityCandidate],
        other_entities: list[EntityCandidate],
    ) -> list[tuple[EntityCandidate, EntityCandidate, float]]:
        """无社区信息时的全局 fallback。"""
        other_by_type: dict[str, list[EntityCandidate]] = {}
        for e in other_entities:
            other_by_type.setdefault(e.entity_type, []).append(e)

        candidates = []
        for ne in new_entities:
            if not ne.embedding:
                continue
            for oe in other_by_type.get(ne.entity_type, []):
                if not oe.embedding:
                    continue
                sim = self._emb.cosine_similarity(ne.embedding, oe.embedding)
                if sim >= self._entity_sim_th:
                    candidates.append((ne, oe, sim))
        return candidates

    # ── 跨书关系候选选择 ─────────────────────────────────────

    def _find_cross_relation_candidates(
        self,
        new_entities: list[EntityCandidate],
        other_entities: list[EntityCandidate],
        matched_pairs: list[tuple[CommunityInfo, CommunityInfo, float]],
        entity_match_pairs: list[tuple[EntityCandidate, EntityCandidate, float]] | None = None,
    ) -> list[tuple[EntityCandidate, EntityCandidate, float]]:
        """找跨书语义关系候选。

        优化策略:
        1. 类型矩阵预筛 — 只保留 VALID_CROSS_RELATION_COMBOS 中合法的 (src_type, tgt_type) 对
        2. 去重 — 排除已进入实体消歧的同类型对
        3. 仅在匹配社区内搜索 — 去掉全局 O(N×M) 暴力扫描
        """
        # 预构建：消歧已有的实体对（同类型、已判断过），避免重复送 LLM
        entity_match_keys: set[tuple[str, str]] = set()
        if entity_match_pairs:
            for ne, oe, _ in entity_match_pairs:
                entity_match_keys.add((ne.name, oe.name))
                entity_match_keys.add((oe.name, ne.name))

        # 预构建：其他书实体按类型分组，加速查找
        other_by_type: dict[str, list[EntityCandidate]] = {}
        for e in other_entities:
            if e.embedding:
                other_by_type.setdefault(e.entity_type, []).append(e)

        # 收集匹配社区覆盖的实体名
        new_comm_entities: dict[str, set[str]] = {}
        other_comm_entities: dict[str, set[str]] = {}
        for nc, oc, _ in matched_pairs:
            new_comm_entities.setdefault(nc.community_id, set(nc.entity_names))
            other_comm_entities.setdefault(oc.community_id, set(oc.entity_names))

        entity_by_name = {e.name: e for e in new_entities + other_entities}
        seen: set[tuple[str, str]] = set()
        candidates: list[tuple[EntityCandidate, EntityCandidate, float]] = []

        # 策略 1: 匹配社区间 + 类型矩阵预筛
        for nc, oc, _ in matched_pairs:
            new_names = new_comm_entities.get(nc.community_id, set())
            other_names = other_comm_entities.get(oc.community_id, set())

            for nn in new_names:
                ne = entity_by_name.get(nn)
                if not ne or not ne.embedding:
                    continue
                for on in other_names:
                    oe = entity_by_name.get(on)
                    if not oe or not oe.embedding:
                        continue
                    key = (nn, on)
                    if key in seen:
                        continue
                    seen.add(key)
                    # 类型矩阵预筛：跳过不合法的类型组合
                    if (ne.entity_type, oe.entity_type) not in VALID_CROSS_RELATION_COMBOS:
                        continue
                    # 去重：已在消歧中判断过的同类型对
                    if key in entity_match_keys:
                        continue
                    sim = self._emb.cosine_similarity(ne.embedding, oe.embedding)
                    if sim >= self._cross_rel_th:
                        candidates.append((ne, oe, sim))

        # 策略 2: 全局兜底 — 仅对匹配社区外的实体，按类型矩阵 + 高阈值
        comm_entity_names = set()
        for names in new_comm_entities.values():
            comm_entity_names.update(names)
        for names in other_comm_entities.values():
            comm_entity_names.update(names)

        for ne in new_entities:
            if not ne.embedding or ne.name in comm_entity_names:
                continue
            # 只看合法目标类型
            for (src_t, tgt_t) in VALID_CROSS_RELATION_COMBOS:
                if src_t != ne.entity_type:
                    continue
                for oe in other_by_type.get(tgt_t, []):
                    if not oe.embedding or oe.name in comm_entity_names:
                        continue
                    key = (ne.name, oe.name)
                    if key in seen:
                        continue
                    seen.add(key)
                    if key in entity_match_keys:
                        continue
                    sim = self._emb.cosine_similarity(ne.embedding, oe.embedding)
                    if sim >= 0.6:
                        candidates.append((ne, oe, sim))

        return candidates

    # ── 批量 LLM 精判 ───────────────────────────────────────

    async def _batch_judge_entity_matches(
        self,
        pairs: list[tuple[EntityCandidate, EntityCandidate, float]],
        batch_size: int = 50,
    ) -> list[EntityMatchCandidate]:
        """批量判断实体消歧。一次 LLM 调用判断多对，batch 间并发。"""
        import asyncio
        import os
        max_concurrent = int(os.environ.get("PHASE5A_LLM_CONCURRENCY", "10"))
        sem = asyncio.Semaphore(max_concurrent)

        async def _judge_batch(batch):
            async with sem:
                try:
                    return await self._llm_judge_entity_batch(batch)
                except Exception as e:
                    logger.warning("实体消歧 batch 调用失败: %s", e)
                    return []

        batches = [
            pairs[i:i + batch_size]
            for i in range(0, len(pairs), batch_size)
        ]

        results = []
        async with asyncio.TaskGroup() as tg:
            judge_tasks = [tg.create_task(_judge_batch(b)) for b in batches]
        for t in judge_tasks:
            try:
                results.extend(t.result())
            except Exception as e:
                logger.warning("实体消歧并发 batch 异常: %s", e)

        for idx, r in enumerate(results):
            r.index = idx
        return results

    async def _llm_judge_entity_batch(
        self,
        pairs: list[tuple[EntityCandidate, EntityCandidate, float]],
    ) -> list[EntityMatchCandidate]:
        """一次 LLM 调用判断多个实体对是否相同概念。"""
        if not self._llm or not pairs:
            return []

        pairs_text = ""
        for i, (ne, oe, sim) in enumerate(pairs):
            pairs_text += f"""
候选 {i+1}:
  实体A: {ne.name} ({ne.entity_type}) — {ne.description[:100]}
  实体B: {oe.name} ({oe.entity_type}) — {oe.description[:100]}
  相似度: {sim:.2f}
"""

        prompt = f"""判断以下 {len(pairs)} 对来自不同书籍的实体是否指代同一概念。

{pairs_text}

请输出 JSON 数组，每个元素对应一个候选:
[
  {{"index": 1, "same": true/false, "reason": "简要说明"}},
  ...
]

规则:
- 两者指代完全相同的概念/事物 → same=true
- 只是相关但不是同一概念 → same=false
- 不确定 → same=false"""

        try:
            response = await self._llm.generate(prompt=prompt, model="qwen-turbo")
            parsed = self._parse_json_array(response)
            results = []
            for item in (parsed or []):
                idx = item.get("index", 1) - 1
                if 0 <= idx < len(pairs):
                    ne, oe, sim = pairs[idx]
                    llm_judge = item.get("same", False)
                    results.append(EntityMatchCandidate(
                        index=idx,
                        new_entity=ne.name,
                        new_type=ne.entity_type,
                        new_desc=ne.description,
                        new_book_id=ne.book_id,
                        matched_entity=oe.name,
                        matched_type=oe.entity_type,
                        matched_desc=oe.description,
                        matched_book_id=oe.book_id,
                        matched_book_title="",
                        similarity=sim,
                        llm_same=llm_judge,
                        llm_reason=item.get("reason", ""),
                        reviewer_decision=self._entity_initial_decision(sim, llm_judge),
                    ))
            return [r for r in results if r.llm_same]
        except Exception as e:
            logger.warning("批量实体消歧失败: %s", e)
            # fallback: 高相似度自动通过
            return [EntityMatchCandidate(
                index=i, new_entity=ne.name, new_type=ne.entity_type,
                new_desc=ne.description, new_book_id=ne.book_id,
                matched_entity=oe.name,
                matched_type=oe.entity_type, matched_desc=oe.description,
                matched_book_id=oe.book_id, matched_book_title="",
                similarity=sim, llm_same=True, llm_reason="高相似度自动匹配",
                reviewer_decision="auto",
            ) for i, (ne, oe, sim) in enumerate(pairs) if sim >= 0.95]

    async def _batch_judge_cross_relations(
        self,
        pairs: list[tuple[EntityCandidate, EntityCandidate, float]],
        batch_size: int = 50,
    ) -> list[CrossRelationCandidate]:
        """批量判断跨书关系。一次 LLM 调用判断多对，batch 间并发。"""
        import asyncio
        import os
        max_concurrent = int(os.environ.get("PHASE5A_LLM_CONCURRENCY", "10"))
        sem = asyncio.Semaphore(max_concurrent)

        async def _judge_batch(batch):
            async with sem:
                try:
                    return await self._llm_judge_cross_relation_batch(batch)
                except Exception as e:
                    logger.warning("跨书关系 batch 调用失败: %s", e)
                    return []

        batches = [
            pairs[i:i + batch_size]
            for i in range(0, len(pairs), batch_size)
        ]

        results = []
        async with asyncio.TaskGroup() as tg:
            judge_tasks = [tg.create_task(_judge_batch(b)) for b in batches]
        for t in judge_tasks:
            try:
                results.extend(t.result())
            except Exception as e:
                logger.warning("跨书关系并发 batch 异常: %s", e)

        for idx, r in enumerate(results):
            r.index = idx
        return results

    async def _llm_judge_cross_relation_batch(
        self,
        pairs: list[tuple[EntityCandidate, EntityCandidate, float]],
    ) -> list[CrossRelationCandidate]:
        """一次 LLM 调用判断多个实体对之间的跨书关系。"""
        if not self._llm or not pairs:
            return []

        pairs_text = ""
        for i, (ne, oe, sim) in enumerate(pairs):
            pairs_text += f"""
候选 {i+1}:
  实体A: {ne.name} ({ne.entity_type}) — {ne.description[:120]}
  实体B: {oe.name} ({oe.entity_type}) — {oe.description[:120]}
  相似度: {sim:.2f}
"""

        all_rel_types = ", ".join(sorted(CROSS_BOOK_RELATION_TYPES))

        prompt = f"""判断以下 {len(pairs)} 对来自不同书籍的实体之间是否存在语义关系。

{pairs_text}

可选关系类型: {all_rel_types}

请输出 JSON 数组:
[
  {{
    "index": 1,
    "has_relation": true/false,
    "relation_type": "关系类型",
    "confidence": 0.0-1.0,
    "reason": "简要说明"
  }},
  ...
]

规则:
- 如果没有明显关系，has_relation 设为 false
- 关系类型优先从可选列表中选择，若无匹配可自行定义
- confidence 表示置信度"""

        try:
            response = await self._llm.generate(prompt=prompt, model="qwen-turbo")
            parsed = self._parse_json_array(response)
            results = []
            for item in (parsed or []):
                idx = item.get("index", 1) - 1
                if 0 <= idx < len(pairs) and item.get("has_relation"):
                    ne, oe, sim = pairs[idx]
                    conf = item.get("confidence", 0.5)
                    results.append(CrossRelationCandidate(
                        index=idx,
                        source_entity=ne.name,
                        source_type=ne.entity_type,
                        source_book=ne.book_id,
                        target_entity=oe.name,
                        target_type=oe.entity_type,
                        target_book=oe.book_id,
                        relation_type=item.get("relation_type", ""),
                        confidence=conf,
                        reason=item.get("reason", ""),
                        reviewer_decision=self._relation_initial_decision(conf),
                    ))
            return results
        except Exception as e:
            logger.warning("批量跨书关系判断失败: %s", e)
            return []

    # ── 辅助方法 ─────────────────────────────────────────────

    def _parse_json_array(self, response: str) -> list[dict] | None:
        """解析 LLM 返回的 JSON 数组。"""
        import re
        match = re.search(r'\[.*\]', response, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
        # fallback: 尝试逐个解析 JSON 对象
        objects = re.findall(r'\{[^{}]*\}', response)
        if objects:
            results = []
            for obj_str in objects:
                try:
                    results.append(json.loads(obj_str))
                except json.JSONDecodeError:
                    pass
            return results if results else None
        return None

    async def _get_source_books(self, book_id: str) -> list[dict]:
        query = """
        MATCH (b:Book)
        WHERE b.book_id <> $book_id
        RETURN b.book_id AS book_id, b.title AS title
        """
        async with self._neo4j.session() as session:
            result = await session.run(query, book_id=book_id)
            return await result.data()

    # ── DESIGN-1: 高置信度自动决策 ──────────────────────────

    @staticmethod
    def _entity_initial_decision(similarity: float, llm_same: bool | None) -> str:
        """实体消歧的初始 reviewer_decision。

        similarity >= 0.95 且 LLM 确认 → 自动合并（"auto"）
        其余 → 待审核（"skip"）
        """
        if similarity >= 0.95 and llm_same:
            return "auto"
        return "skip"

    @staticmethod
    def _relation_initial_decision(confidence: float) -> str:
        """跨书关系的初始 reviewer_decision。

        confidence >= 0.90 → 自动确认（"auto"）
        其余 → 待审核（"skip"）
        """
        if confidence >= 0.90:
            return "auto"
        return "skip"

    def _save_to_json(self, result: CrossBookAnalysisResult, output_dir: str) -> None:
        """保存跨书分析结果到 JSON 文件。

        修复 RACE-1: 写入前先读取已有 JSON，保留已有的 reviewer_decision。
        修复 RACE-2: 原子写入（先写 .tmp 再 os.replace）。
        """
        import os as _os

        output_path = Path(output_dir) / result.book_id / "cross_book_relations.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # ── RACE-1: 读取已有决策，合并保留 ──
        existing_decisions: dict[tuple, str] = {}
        if output_path.exists():
            try:
                existing = json.loads(output_path.read_text("utf-8"))
                for m in existing.get("entity_matches", []):
                    key = (m.get("new_entity", ""), m.get("matched_entity", ""))
                    if key[0] and key[1]:
                        existing_decisions[("em", key[0], key[1])] = m.get(
                            "reviewer_decision", "skip"
                        )
                for r in existing.get("cross_relations", []):
                    key = (r.get("source_entity", ""), r.get("target_entity", ""))
                    if key[0] and key[1]:
                        existing_decisions[("cr", key[0], key[1])] = r.get(
                            "reviewer_decision", "skip"
                        )
            except Exception:
                pass  # 文件损坏 → 全量覆盖

        # 合并：保留已有决策，新候选保持默认
        for m in result.entity_matches:
            key = ("em", m.new_entity, m.matched_entity)
            if key in existing_decisions:
                m.reviewer_decision = existing_decisions[key]
        for r in result.cross_relations:
            key = ("cr", r.source_entity, r.target_entity)
            if key in existing_decisions:
                r.reviewer_decision = existing_decisions[key]

        retained = len(existing_decisions)
        if retained:
            logger.info("Phase 5a: 已保留 %d 条审核决策", retained)

        data = {
            "book_id": result.book_id,
            "generated_at": result.generated_at,
            "source_books": result.source_books,
            "entity_matches": [asdict(m) for m in result.entity_matches],
            "cross_relations": [asdict(r) for r in result.cross_relations],
            "stats": {
                "total_new_entities": result.total_new_entities,
                "total_other_entities": result.total_other_entities,
                "match_candidates": result.match_candidates_count,
                "relation_candidates": result.relation_candidates_count,
            },
        }

        # ── RACE-2: 原子写入 ──
        tmp_path = output_path.with_suffix(".json.tmp")
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        _os.replace(str(tmp_path), str(output_path))
        logger.info("Phase 5a 结果已保存: %s", output_path)

    def _save_to_redis(self, result: CrossBookAnalysisResult) -> None:
        try:
            import redis
            r = get_sync_redis()
            key = f"d2g:cross_analysis:{result.book_id}"
            data = {
                "book_id": result.book_id,
                "generated_at": result.generated_at,
                "entity_matches": [asdict(m) for m in result.entity_matches],
                "cross_relations": [asdict(r) for r in result.cross_relations],
            }
            r.setex(key, 86400 * 30, json.dumps(data, ensure_ascii=False))
        except Exception as e:
            logger.warning("Redis 保存失败: %s", e)


# ── 便捷函数 ─────────────────────────────────────────────────


async def run_phase5a_cross_book_analysis(
    book_id: str,
    neo4j_driver,
    embedding_helper=None,
    llm_client=None,
    output_dir: str | None = None,
) -> CrossBookAnalysisResult:
    engine = CrossBookPhase5a(
        neo4j_driver=neo4j_driver,
        embedding_helper=embedding_helper,
        llm_client=llm_client,
    )
    return await engine.run_phase5a(book_id, output_dir)
