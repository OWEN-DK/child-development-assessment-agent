"""⚠️ DEPRECATED (2026-06): 已被 cross_book_phase5a.py + cross_book_phase5b.py 替代。
新路径: Phase 5a 做跨书匹配+关系发现, Phase 5b 执行审核者决策。
旧路径仅支持 3 种跨书关系类型，保留仅供向后兼容和测试。

跨书实体消歧引擎（Phase 5）— 跨书 embedding 粗筛 + LLM 精判 + 合并/SAME_AS 执行。

放置位置: backend/src/core/knowledge_qa/neo4j/cross_book_resolver.py
依赖:
  - D2G Phase 4 入库完成（Neo4j 中已有新书实体）
  - embedding 缓存（复用 D2G Phase 1-2 的 embedding）
  - LLM 客户端（DashScope qwen-turbo）

设计文档: docs/architecture/08-知识图谱多书扩展方案.md §2-4
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol

logger = logging.getLogger(__name__)

# ── 常量 ──────────────────────────────────────────────────────

D2G_LABELS = [
    "Problem", "Solution", "BrainRegion", "Risk", "Exercise",
    "RootCause", "Prescription", "ChildProfile",
    "CognitiveProcess", "Theory", "Mechanism",
    "DevelopmentalStage", "Strategy", "KeyInsight", "ResearchFinding",
]
"""D2G 支持的全部 15 种实体类型标签。"""

HIGH_SIMILARITY_THRESHOLD = 0.9
MID_SIMILARITY_THRESHOLD = 0.7


# ── Protocol ─────────────────────────────────────────────────


class EmbeddingHelper(Protocol):
    async def embed_text(self, text: str) -> list[float] | None: ...
    def cosine_similarity(self, a: list[float], b: list[float]) -> float: ...


class LLMClient(Protocol):
    async def generate(self, prompt: str, model: str) -> str: ...


# ── 数据结构 ─────────────────────────────────────────────────


@dataclass
class EntityCandidate:
    """Neo4j 中的一个实体节点。"""
    name: str
    name_normalized: str
    entity_type: str
    description: str
    book_id: str
    book_ids: list[str] = field(default_factory=list)


@dataclass
class SimilarityPair:
    """一对相似实体 + 相似度。"""
    new_entity: EntityCandidate
    existing_entity: EntityCandidate
    similarity: float
    llm_same: bool | None = None
    llm_reason: str = ""


@dataclass
class ReviewerDecision:
    """审核者对某个跨书匹配的决策。"""
    entity_name: str
    matched_entity_name: str
    matched_book_id: str
    decision: str  # "merge" / "separate" / "skip"


@dataclass
class Phase5Outcome:
    """Phase 5 执行结果。"""
    book_id: str
    total_entities: int = 0
    high_sim_pairs: int = 0
    mid_sim_pairs: int = 0
    merged_count: int = 0
    same_as_count: int = 0
    reviewer_override_count: int = 0
    cross_book_relations: int = 0
    duration_ms: int = 0
    errors: list[str] = field(default_factory=list)


# ── 核心引擎 ─────────────────────────────────────────────────


class CrossBookResolver:
    """跨书实体消歧引擎。

    执行流程（§08-4.2）:
    1. 加载新书实体 + 其他书实体
    2. 加载审核者决策
    3. embedding 粗筛 → 分三档
    4. LLM 精判（similarity >= 0.7 的候选）
    5. 执行合并/建边（优先审核者决策）
    6. 跨书关系检测（CONSENSUS/COMPLEMENTS/CONFLICTS）
    """

    def __init__(
        self,
        neo4j_driver,
        embedding_helper: EmbeddingHelper | None = None,
        llm_client: LLMClient | None = None,
        high_threshold: float = HIGH_SIMILARITY_THRESHOLD,
        mid_threshold: float = MID_SIMILARITY_THRESHOLD,
    ):
        self._neo4j = neo4j_driver
        self._emb = embedding_helper
        self._llm = llm_client
        self._high_th = high_threshold
        self._mid_th = mid_threshold

    # ── 公开接口 ──────────────────────────────────────────────

    async def run_phase5(
        self,
        book_id: str,
        reviewer_decisions: list[ReviewerDecision] | None = None,
    ) -> Phase5Outcome:
        """Phase 5 主入口。在 Phase 4 入库完成后调用。

        Args:
            book_id: 新入库书籍 ID
            reviewer_decisions: 审核者在审核 MD 中标记的跨书匹配决策

        Returns:
            Phase5Outcome 执行结果
        """
        start = time.monotonic()
        outcome = Phase5Outcome(book_id=book_id)

        try:
            # Step 1: 加载数据
            new_entities = self._load_book_entities(book_id)
            outcome.total_entities = len(new_entities)

            if not new_entities:
                logger.info("新书 %s 无实体，跳过 Phase 5", book_id)
                return outcome

            other_entities = self._load_other_entities(book_id)
            if not other_entities:
                logger.info("Neo4j 中无其他书实体，跳过 Phase 5")
                return outcome

            # Step 2: 加载审核者决策
            decisions_map: dict[tuple[str, str, str], str] = {}
            if reviewer_decisions:
                for d in reviewer_decisions:
                    key = (d.entity_name, d.matched_entity_name, d.matched_book_id)
                    decisions_map[key] = d.decision

            # Step 3: embedding 粗筛
            pairs = await self._compute_similarity(new_entities, other_entities)
            high_pairs = [p for p in pairs if p.similarity >= self._high_th]
            mid_pairs = [p for p in pairs if self._mid_th <= p.similarity < self._high_th]
            outcome.high_sim_pairs = len(high_pairs)
            outcome.mid_sim_pairs = len(mid_pairs)

            logger.info(
                "Phase 5 粗筛: %d 对高相似, %d 对中相似 (共 %d 对)",
                len(high_pairs), len(mid_pairs), len(pairs),
            )

            # Step 4: LLM 精判
            candidates = high_pairs + mid_pairs
            if self._llm and candidates:
                await self._llm_judge_batch(candidates)

            # Step 5: 执行合并/建边
            for pair in candidates:
                key = (
                    pair.new_entity.name,
                    pair.existing_entity.name,
                    pair.existing_entity.book_id,
                )
                decision = decisions_map.get(key, "skip")

                if decision == "merge":
                    # 审核者决策：合并
                    success = self._execute_merge(pair.new_entity, pair.existing_entity)
                    if success:
                        outcome.merged_count += 1
                        outcome.reviewer_override_count += 1
                elif decision == "separate":
                    # 审核者决策：独立（不处理）
                    outcome.reviewer_override_count += 1
                else:
                    # 自动阈值处理
                    if pair.similarity >= self._high_th and pair.llm_same:
                        success = self._execute_merge(pair.new_entity, pair.existing_entity)
                        if success:
                            outcome.merged_count += 1
                    elif pair.similarity >= self._mid_th and pair.llm_same:
                        self._execute_same_as(pair.new_entity, pair.existing_entity, pair)
                        outcome.same_as_count += 1

            # Step 6: 跨书关系检测（SAME_AS 实体对）
            from src.core.knowledge_qa.neo4j.cross_relation import (
                detect_cross_book_relations_for_same_as,
            )
            if self._llm:
                try:
                    relations = await detect_cross_book_relations_for_same_as(
                        self._neo4j, self._llm,
                    )
                    outcome.cross_book_relations = len(relations)
                except Exception as e:
                    logger.warning("跨书关系检测失败: %s", e)
                    outcome.errors.append(f"cross_relation: {e}")

            # Step 7: 持久化消歧结果到 Redis
            self._persist_result(outcome)

        except Exception as e:
            logger.exception("Phase 5 执行异常: %s", e)
            outcome.errors.append(str(e))

        outcome.duration_ms = int((time.monotonic() - start) * 1000)
        logger.info(
            "Phase 5 完成: book=%s, merged=%d, same_as=%d, relations=%d, "
            "reviewer_override=%d, duration=%dms",
            book_id, outcome.merged_count, outcome.same_as_count,
            outcome.cross_book_relations, outcome.reviewer_override_count,
            outcome.duration_ms,
        )
        return outcome

    # ── 数据加载 ──────────────────────────────────────────────

    def _load_book_entities(self, book_id: str) -> list[EntityCandidate]:
        """加载指定书籍的所有 D2G 类型实体。"""
        with self._neo4j.session() as session:
            records = session.run(
                """
                MATCH (n)
                WHERE any(label IN labels(n) WHERE label IN $labels)
                  AND $book_id IN coalesce(n.book_ids, [n.book_id])
                RETURN n.name AS name, n.name_normalized AS name_norm,
                       labels(n)[0] AS entity_type,
                       n.description AS desc, n.book_id AS book_id,
                       coalesce(n.book_ids, [n.book_id]) AS book_ids
                """,
                labels=D2G_LABELS, book_id=book_id,
            ).data()
        return [self._record_to_entity(r) for r in records]

    def _load_other_entities(self, exclude_book_id: str) -> list[EntityCandidate]:
        """加载除指定书籍外的所有 D2G 类型实体。"""
        with self._neo4j.session() as session:
            records = session.run(
                """
                MATCH (n)
                WHERE any(label IN labels(n) WHERE label IN $labels)
                  AND NOT $book_id IN coalesce(n.book_ids, [n.book_id])
                RETURN n.name AS name, n.name_normalized AS name_norm,
                       labels(n)[0] AS entity_type,
                       n.description AS desc, n.book_id AS book_id,
                       coalesce(n.book_ids, [n.book_id]) AS book_ids
                """,
                labels=D2G_LABELS, book_id=exclude_book_id,
            ).data()
        return [self._record_to_entity(r) for r in records]

    @staticmethod
    def _record_to_entity(r: dict) -> EntityCandidate:
        return EntityCandidate(
            name=r.get("name", ""),
            name_normalized=r.get("name_norm", r.get("name", "").strip().lower()),
            entity_type=r.get("entity_type", ""),
            description=r.get("desc", ""),
            book_id=r.get("book_id", ""),
            book_ids=r.get("book_ids", []),
        )

    # ── embedding 粗筛 ───────────────────────────────────────

    async def _compute_similarity(
        self,
        new_entities: list[EntityCandidate],
        other_entities: list[EntityCandidate],
    ) -> list[SimilarityPair]:
        """对新书实体与已有实体计算 embedding cosine similarity。"""
        if not self._emb:
            # 降级：名称精确匹配
            return self._name_based_matching(new_entities, other_entities)

        pairs: list[SimilarityPair] = []

        # 预计算新书实体 embedding
        new_embs: dict[str, list[float]] = {}
        for e in new_entities:
            key = e.name_normalized
            if key not in new_embs:
                emb = await self._emb.embed_text(f"{e.name} {e.description[:200]}")
                if emb:
                    new_embs[key] = emb
        # 批量获取已有实体 Embeddings
        all_embs = await self._emb.embed_batch([
            f"{e.name} {e.description[:200]}" for e in other_entities
        ])

        # 预计算已有实体 embedding（按 name_normalized 去重）
        other_embs: dict[str, list[float]] = {}
        for e in other_entities:
            key = e.name_normalized
            if key not in other_embs:
                emb = await self._emb.embed_text(f"{e.name} {e.description[:200]}")
                if emb:
                    other_embs[key] = emb

        # 计算 pairwise similarity
        for new_e in new_entities:
            new_emb = new_embs.get(new_e.name_normalized)
            if not new_emb:
                continue
            for other_e in other_entities:
                if new_e.name_normalized == other_e.name_normalized:
                    # 名称完全匹配，直接高相似
                    pairs.append(SimilarityPair(
                        new_entity=new_e, existing_entity=other_e, similarity=1.0,
                    ))
                    continue
                other_emb = other_embs.get(other_e.name_normalized)
                if not other_emb:
                    continue
                sim = self._emb.cosine_similarity(new_emb, other_emb)
                if sim >= self._mid_th:
                    pairs.append(SimilarityPair(
                        new_entity=new_e, existing_entity=other_e, similarity=sim,
                    ))

        # 按 similarity 降序
        pairs.sort(key=lambda p: p.similarity, reverse=True)
        return pairs

    def _name_based_matching(
        self,
        new_entities: list[EntityCandidate],
        other_entities: list[EntityCandidate],
    ) -> list[SimilarityPair]:
        """降级：基于名称的粗筛（无 embedding 时）。"""
        other_map: dict[str, list[EntityCandidate]] = {}
        for e in other_entities:
            other_map.setdefault(e.name_normalized, []).append(e)

        pairs = []
        for new_e in new_entities:
            # 精确匹配
            for other_e in other_map.get(new_e.name_normalized, []):
                pairs.append(SimilarityPair(
                    new_entity=new_e, existing_entity=other_e, similarity=1.0,
                ))
            # 包含匹配（括号别名）
            for norm, entities in other_map.items():
                if norm == new_e.name_normalized:
                    continue
                if (new_e.name_normalized in norm or norm in new_e.name_normalized):
                    for other_e in entities:
                        pairs.append(SimilarityPair(
                            new_entity=new_e, existing_entity=other_e, similarity=0.85,
                        ))

        return pairs

    # ── LLM 精判 ─────────────────────────────────────────────

    async def _llm_judge_batch(self, pairs: list[SimilarityPair]) -> None:
        """对候选对执行 LLM 精判（批量，限制并发）。"""
        for pair in pairs:
            try:
                prompt = (
                    "判断以下两个来自不同书籍的实体是否指代同一概念。\n\n"
                    f"实体 A: {pair.new_entity.name} — {pair.new_entity.description[:300]}\n"
                    f"实体 B: {pair.existing_entity.name} — {pair.existing_entity.description[:300]}\n\n"
                    "输出 JSON: {\"same\": true/false, \"reason\": \"简要说明\"}"
                )
                response = await self._llm.generate(prompt=prompt, model="qwen3.5-27b")

                # 解析 JSON
                import re
                json_match = re.search(r'\{[^{}]*\}', response)
                if json_match:
                    result = json.loads(json_match.group())
                    pair.llm_same = result.get("same", False)
                    pair.llm_reason = result.get("reason", "")
                else:
                    pair.llm_same = False
                    pair.llm_reason = "LLM 返回无法解析"
            except Exception as e:
                logger.warning("LLM 精判失败: %s", e)
                pair.llm_same = False
                pair.llm_reason = f"LLM error: {e}"

    # ── 合并执行 ─────────────────────────────────────────────

    async def _execute_merge(
        self, new_entity: EntityCandidate, existing_entity: EntityCandidate,
    ) -> bool:
        """在 Neo4j 事务内执行实体合并（§08-2.3）。

        将 new_entity 合并到 existing_entity 中，迁移所有关系。
        """
        try:
            async with self._neo4j.session() as session:
                session.execute_write(
                    self._merge_tx, new_entity, existing_entity,
                )
            logger.info(
                "合并成功: '%s' (%s) → '%s' (%s)",
                new_entity.name, new_entity.book_id,
                existing_entity.name, existing_entity.book_id,
            )
            return True
        except Exception as e:
            logger.error("合并失败: '%s' → '%s': %s", new_entity.name, existing_entity.name, e)
            return False

    @staticmethod
    def _merge_tx(tx, new_entity: EntityCandidate, existing_entity: EntityCandidate):
        """Neo4j 事务函数：执行合并的全部 Cypher 操作。

        Step 1-2 为本引擎特有（MergeLog + 属性合并），
        Step 3-7 委托给 relation_migration 共享模块。
        """
        from .relation_migration import build_migration_cypher_sync

        merge_id = str(uuid.uuid4())

        # Step 1: 创建 MergeLog 节点
        tx.run(
            """
            MATCH (old {name: $old_name})
            WHERE $old_book_id IN coalesce(old.book_ids, [old.book_id])
            MATCH (new {name: $new_name})
            WHERE $new_book_id IN coalesce(new.book_ids, [new.book_id])
            CREATE (log:MergeLog {
                merge_id: $merge_id,
                target_entity: old.name,
                source_entity: new.name,
                source_book_id: new.book_id,
                original_description: new.description,
                original_book_ids: coalesce(new.book_ids, [new.book_id]),
                merged_at: datetime()
            })
            CREATE (old)-[:MERGED_FROM]->(log)
            """,
            old_name=existing_entity.name,
            old_book_id=existing_entity.book_id,
            new_name=new_entity.name,
            new_book_id=new_entity.book_id,
            merge_id=merge_id,
        )

        # Step 2: 合并属性
        tx.run(
            """
            MATCH (old {name: $old_name})
            WHERE $old_book_id IN coalesce(old.book_ids, [old.book_id])
            MATCH (new {name: $new_name})
            WHERE $new_book_id IN coalesce(new.book_ids, [new.book_id])
            SET old.description = CASE
                WHEN size(old.description) > 1.5 * size(new.description) THEN old.description
                WHEN size(new.description) > 1.5 * size(old.description) THEN new.description
                ELSE old.description + '---' + new.description
            END
            SET old.book_ids = coalesce(old.book_ids, [old.book_id]) + coalesce(new.book_ids, [new.book_id])
            """,
            old_name=existing_entity.name,
            old_book_id=existing_entity.book_id,
            new_name=new_entity.name,
            new_book_id=new_entity.book_id,
        )

        # Step 3-7: 关系迁移 + 删除（共用模块）
        stmts = build_migration_cypher_sync(
            tx,
            new_name=new_entity.name,
            new_book_id=new_entity.book_id,
            existing_name=existing_entity.name,
            existing_book_id=existing_entity.book_id,
        )
        for cypher, params in stmts:
            tx.run(cypher, **params)

    # ── SAME_AS 建边 ─────────────────────────────────────────

    async def _execute_same_as(
        self,
        new_entity: EntityCandidate,
        existing_entity: EntityCandidate,
        pair: SimilarityPair,
    ) -> None:
        """创建 SAME_AS 边（§08-2.4）。"""
        merge_id = str(uuid.uuid4())
        try:
            async with self._neo4j.session() as session:
                session.run(
                    """
                    MATCH (a {name: $name_a})
                    WHERE $book_a IN coalesce(a.book_ids, [a.book_id])
                    MATCH (b {name: $name_b})
                    WHERE $book_b IN coalesce(b.book_ids, [b.book_id])
                    MERGE (a)-[r:SAME_AS]->(b)
                    SET r.confidence = $similarity,
                        r.created_by = 'd2g_phase5',
                        r.merge_id = $merge_id,
                        r.llm_reason = $reason,
                        r.created_at = datetime()
                    """,
                    name_a=new_entity.name,
                    book_a=new_entity.book_id,
                    name_b=existing_entity.name,
                    book_b=existing_entity.book_id,
                    similarity=pair.similarity,
                    merge_id=merge_id,
                    reason=pair.llm_reason or "",
                )
            logger.info(
                "SAME_AS 边创建: '%s' ↔ '%s' (sim=%.2f)",
                new_entity.name, existing_entity.name, pair.similarity,
            )
        except Exception as e:
            logger.warning(
                "SAME_AS 创建失败: '%s' ↔ '%s': %s",
                new_entity.name, existing_entity.name, e,
            )

    # ── 持久化 ───────────────────────────────────────────────

    def _persist_result(self, outcome: Phase5Outcome) -> None:
        """将消歧结果持久化到 Redis（支持审计）。"""
        try:
            import redis
            from src.config.modules.redis import get_sync_redis
            r = get_sync_redis()
            key = f"d2g:cross_disambig:{outcome.book_id}"
            r.setex(key, 86400 * 7, json.dumps({
                "book_id": outcome.book_id,
                "total_entities": outcome.total_entities,
                "merged_count": outcome.merged_count,
                "same_as_count": outcome.same_as_count,
                "reviewer_override_count": outcome.reviewer_override_count,
                "cross_book_relations": outcome.cross_book_relations,
                "duration_ms": outcome.duration_ms,
                "errors": outcome.errors,
            }, ensure_ascii=False))
        except Exception as e:
            logger.debug("Redis persist failed: %s", e)

    # ── SAME_AS 生命周期 API ─────────────────────────────────

    async def revoke_same_as(self, merge_id: str, reason: str) -> None:
        """撤销指定的 SAME_AS 边（软删除，§08-2.7.1）。"""
        async with self._neo4j.session() as session:
            session.run(
                """
                MATCH ()-[r:SAME_AS {merge_id: $merge_id}]->()
                SET r.revoked = true, r.revoked_at = datetime(), r.revoke_reason = $reason
                """,
                merge_id=merge_id, reason=reason,
            )
        logger.info("SAME_AS 已撤销: merge_id=%s, reason=%s", merge_id, reason)

    async def list_active_same_as(self, entity_name: str) -> list[dict]:
        """查询某实体的所有活跃 SAME_AS 关联（过滤已撤销）。"""
        async with self._neo4j.session() as session:
            return session.run(
                """
                MATCH (n {name: $name})-[r:SAME_AS]-(related)
                WHERE NOT coalesce(r.revoked, false)
                RETURN related.name AS name, related.book_id AS book_id,
                       r.confidence AS confidence, r.llm_reason AS reason
                """,
                name=entity_name,
            ).data()

    async def upgrade_same_as_to_merge(self, name_a: str, book_a: str, name_b: str, book_b: str) -> bool:
        """将 SAME_AS 对升级为合并（§08-2.7.1）。"""
        new = EntityCandidate(
            name=name_b, name_normalized=name_b.strip().lower(),
            entity_type="", description="", book_id=book_b,
        )
        existing = EntityCandidate(
            name=name_a, name_normalized=name_a.strip().lower(),
            entity_type="", description="", book_id=book_a,
        )
        # 先删除 SAME_AS 边
        async with self._neo4j.session() as session:
            session.run(
                """
                MATCH (a {name: $name_a})-[r:SAME_AS]-(b {name: $name_b})
                DELETE r
                """,
                name_a=name_a, name_b=name_b,
            )
        # 执行合并
        return self._execute_merge(new, existing)
