"""Phase 5b: 执行审核者决策 — 合并实体/建边/创建跨书关系。

放置位置: backend/src/core/knowledge_qa/neo4j/cross_book_phase5b.py
依赖:
  - Phase 5a 分析结果（从 Redis/JSON 读取）
  - 审核者决策

设计文档: docs/architecture/13-跨书知识融合方案-v2.md §6
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol

from .schema import CROSS_BOOK_RELATION_TYPES

logger = logging.getLogger(__name__)


# ── Protocol ─────────────────────────────────────────────────


class Neo4jDriver(Protocol):
    def session(self) -> Any: ...


# ── 数据结构 ─────────────────────────────────────────────────


@dataclass
class EntityMatchDecision:
    """实体消歧决策。"""
    index: int
    new_entity: str
    new_type: str
    new_book_id: str  # 新实体所属的 book_id（修复 BUG-1）
    matched_entity: str
    matched_type: str
    matched_book_id: str
    similarity: float
    llm_same: bool | None
    reviewer_decision: str  # merge / separate / auto / skip


@dataclass
class CrossRelationDecision:
    """跨书关系决策。"""
    index: int
    source_entity: str
    source_type: str
    source_book: str
    target_entity: str
    target_type: str
    target_book: str
    relation_type: str
    confidence: float
    reviewer_decision: str  # confirm / ignore / modify / auto / skip


@dataclass
class Phase5bOutcome:
    """Phase 5b 执行结果。"""
    book_id: str
    merged_count: int = 0
    separated_count: int = 0
    auto_merged_count: int = 0
    same_as_count: int = 0
    skipped_count: int = 0
    relations_created: int = 0
    auto_relations: int = 0
    relations_skipped: int = 0
    errors: list[str] = field(default_factory=list)
    duration_ms: int = 0


# ── 核心引擎 ─────────────────────────────────────────────────


class CrossBookPhase5b:
    """Phase 5b 执行决策引擎。

    执行流程:
    1. 从 Redis/JSON 读取 Phase 5a 分析结果
    2. 解析审核者决策
    3. 执行实体消歧决策（合并/独立/跳过）
    4. 执行跨书关系决策（确认/忽略/修改/跳过）
    5. 清理 Redis 缓存
    """

    def __init__(self, neo4j_driver: Neo4jDriver):
        self._neo4j = neo4j_driver

    async def run_phase5b(
        self,
        book_id: str,
        analysis_result: dict | None = None,
    ) -> Phase5bOutcome:
        """Phase 5b 主入口。

        Args:
            book_id: 书籍 ID
            analysis_result: Phase 5a 分析结果（可选，否则从 Redis 读取）

        Returns:
            Phase5bOutcome 执行结果
        """
        start = time.monotonic()
        outcome = Phase5bOutcome(book_id=book_id)

        try:
            # Step 1: 加载分析结果
            if not analysis_result:
                analysis_result = self._load_analysis_result(book_id)

            if not analysis_result:
                logger.info("未找到 Phase 5a 分析结果，跳过 Phase 5b")
                return outcome

            # Step 2: 执行实体消歧决策
            entity_matches = analysis_result.get("entity_matches", [])
            for match in entity_matches:
                decision = EntityMatchDecision(
                    index=match.get("index", 0),
                    new_entity=match.get("new_entity", ""),
                    new_type=match.get("new_type", ""),
                    new_book_id=match.get("new_book_id", ""),
                    matched_entity=match.get("matched_entity", ""),
                    matched_type=match.get("matched_type", ""),
                    matched_book_id=match.get("matched_book_id", ""),
                    similarity=match.get("similarity", 0),
                    llm_same=match.get("llm_same"),
                    reviewer_decision=match.get("reviewer_decision", "skip"),
                )
                await self._execute_entity_match_decision(decision, outcome)

            # Step 3: 执行跨书关系决策
            cross_relations = analysis_result.get("cross_relations", [])
            for rel in cross_relations:
                decision = CrossRelationDecision(
                    index=rel.get("index", 0),
                    source_entity=rel.get("source_entity", ""),
                    source_type=rel.get("source_type", ""),
                    source_book=rel.get("source_book", ""),
                    target_entity=rel.get("target_entity", ""),
                    target_type=rel.get("target_type", ""),
                    target_book=rel.get("target_book", ""),
                    relation_type=rel.get("relation_type", ""),
                    confidence=rel.get("confidence", 0),
                    reviewer_decision=rel.get("reviewer_decision", "skip"),
                )
                await self._execute_cross_relation_decision(decision, outcome)

            # Step 4: 清理 Redis 缓存
            self._cleanup_redis(book_id)

            duration_ms = int((time.monotonic() - start) * 1000)
            outcome.duration_ms = duration_ms

            logger.info(
                "Phase 5b 完成: book_id=%s, 合并=%d, SAME_AS=%d, 关系=%d, 耗时=%dms",
                book_id, outcome.merged_count, outcome.same_as_count,
                outcome.relations_created, duration_ms,
            )

        except Exception as e:
            logger.error("Phase 5b 执行失败: %s", e, exc_info=True)
            outcome.errors.append(str(e))

        return outcome

    # ── 实体消歧决策执行 ─────────────────────────────────────

    async def _execute_entity_match_decision(
        self,
        decision: EntityMatchDecision,
        outcome: Phase5bOutcome,
    ) -> None:
        """执行实体消歧决策。"""
        try:
            if decision.reviewer_decision == "merge":
                # 审核者明确选择合并
                success = await self._execute_entity_merge(decision)
                if success:
                    outcome.merged_count += 1

            elif decision.reviewer_decision == "separate":
                # 审核者明确选择独立
                outcome.separated_count += 1

            elif decision.reviewer_decision == "auto":
                # 委托系统自动处理
                if decision.similarity >= 0.9 and decision.llm_same:
                    success = await self._execute_entity_merge(decision)
                    if success:
                        outcome.auto_merged_count += 1
                elif decision.similarity >= 0.7 and decision.llm_same:
                    await self._create_same_as_edge(decision)
                    outcome.same_as_count += 1

            elif decision.reviewer_decision == "skip":
                # 审核者明确跳过
                outcome.skipped_count += 1

        except Exception as e:
            logger.warning("执行实体消歧决策失败: %s", e)
            outcome.errors.append(f"实体消歧失败: {decision.new_entity} - {e}")

    async def _execute_entity_merge(self, decision: EntityMatchDecision) -> bool:
        """执行实体合并。

        使用 relation_migration 模块的关系迁移逻辑（修复 BUG-2），
        包含幂等检查（修复 PHASE5b-IDEMPOTENCY）。
        """
        from .relation_migration import build_migration_cypher_async

        try:
            async with self._neo4j.session() as session:
                # ── 幂等检查：new 节点是否还存在 ──
                check = await session.run(
                    """
                    MATCH (n {name: $name})
                    WHERE $book_id IN coalesce(n.book_ids, [n.book_id])
                    RETURN n
                    """,
                    name=decision.new_entity, book_id=decision.new_book_id,
                )
                if not await check.single():
                    logger.info(
                        "实体已不存在（可能已被前次合并），视为幂等成功: '%s'",
                        decision.new_entity,
                    )
                    return True  # 幂等：前一次执行已成功合并

                # ── 执行关系迁移 + 合并（6 步事务） ──
                stmts = await build_migration_cypher_async(
                    session,
                    new_name=decision.new_entity,
                    new_book_id=decision.new_book_id,
                    existing_name=decision.matched_entity,
                    existing_book_id=decision.matched_book_id,
                )
                for cypher, params in stmts:
                    await session.run(cypher, **params)

                logger.info(
                    "实体合并成功: '%s' -> '%s'",
                    decision.new_entity, decision.matched_entity,
                )
                return True

        except Exception as e:
            logger.warning("实体合并失败: '%s' -> '%s': %s",
                           decision.new_entity, decision.matched_entity, e)

        return False

    async def _create_same_as_edge(self, decision: EntityMatchDecision) -> None:
        """创建 SAME_AS 边。"""
        try:
            async with self._neo4j.session() as session:
                await session.run(
                    """
                    MATCH (a {name: $name_a})
                    WHERE $book_a IN coalesce(a.book_ids, [a.book_id])
                    MATCH (b {name: $name_b})
                    WHERE $book_b IN coalesce(b.book_ids, [b.book_id])
                    MERGE (a)-[r:SAME_AS]->(b)
                    SET r.confidence = $similarity,
                        r.created_by = 'phase5b',
                        r.source_book = $book_a,
                        r.target_book = $book_b,
                        r.created_at = datetime()
                    """,
                    name_a=decision.new_entity,
                    book_a=decision.new_book_id,
                    name_b=decision.matched_entity,
                    book_b=decision.matched_book_id,
                    similarity=decision.similarity,
                )

                logger.info(
                    "SAME_AS 边创建: '%s' <-> '%s'",
                    decision.new_entity, decision.matched_entity,
                )

        except Exception as e:
            logger.warning("SAME_AS 边创建失败: %s", e)

    # ── 跨书关系决策执行 ─────────────────────────────────────

    async def _execute_cross_relation_decision(
        self,
        decision: CrossRelationDecision,
        outcome: Phase5bOutcome,
    ) -> None:
        """执行跨书关系决策。"""
        try:
            if decision.reviewer_decision == "confirm":
                # 审核者明确确认
                success = await self._create_cross_book_relation(decision)
                if success:
                    outcome.relations_created += 1

            elif decision.reviewer_decision == "modify":
                # 审核者修改关系类型（relation_type 已更新）
                success = await self._create_cross_book_relation(decision)
                if success:
                    outcome.relations_created += 1

            elif decision.reviewer_decision == "auto":
                # 委托系统自动处理
                if decision.confidence >= 0.85:
                    success = await self._create_cross_book_relation(decision)
                    if success:
                        outcome.auto_relations += 1

            elif decision.reviewer_decision == "ignore":
                # 审核者忽略
                pass

            elif decision.reviewer_decision == "skip":
                # 审核者跳过
                outcome.relations_skipped += 1

        except Exception as e:
            logger.warning("执行跨书关系决策失败: %s", e)
            outcome.errors.append(f"跨书关系失败: {decision.source_entity} -> {decision.target_entity} - {e}")

    async def _create_cross_book_relation(self, decision: CrossRelationDecision) -> bool:
        """创建跨书关系边。"""
        # 验证关系类型
        if decision.relation_type not in CROSS_BOOK_RELATION_TYPES:
            logger.warning("无效的跨书关系类型: %s", decision.relation_type)
            return False

        try:
            async with self._neo4j.session() as session:
                await session.run(
                    """
                    MATCH (source {{name: $source_name}})
                    WHERE $source_book IN coalesce(source.book_ids, [source.book_id])
                    MATCH (target {{name: $target_name}})
                    WHERE $target_book IN coalesce(target.book_ids, [target.book_id])
                    MERGE (source)-[r:{relation_type}]->(target)
                    SET r.confidence = $confidence,
                        r.created_by = 'phase5b',
                        r.source_book = $source_book,
                        r.target_book = $target_book,
                        r.created_at = datetime()
                    """.format(relation_type=decision.relation_type),
                    source_name=decision.source_entity,
                    source_book=decision.source_book,
                    target_name=decision.target_entity,
                    target_book=decision.target_book,
                    confidence=decision.confidence,
                )

                logger.info(
                    "跨书关系创建: '%s' -[%s]-> '%s'",
                    decision.source_entity, decision.relation_type, decision.target_entity,
                )
                return True

        except Exception as e:
            logger.warning("跨书关系创建失败: %r", e)

        return False

    # ── 辅助方法 ─────────────────────────────────────────────

    def _load_from_redis(self, book_id: str) -> dict | None:
        """从 Redis 加载 Phase 5a 分析结果。"""
        try:
            import redis
            from src.config.modules.redis import get_sync_redis
            r = get_sync_redis()
            key = f"d2g:cross_analysis:{book_id}"
            data = r.get(key)
            if data:
                return json.loads(data)
        except Exception as e:
            logger.warning("Redis 读取失败: %s", e)
        return None

    def _load_analysis_result(self, book_id: str) -> dict | None:
        """加载 Phase 5a 分析结果：Redis 优先，JSON 文件兜底。

        修复：Redis 30 天 TTL 过期后仍可从 JSON 文件读取，
        避免分析结果永久丢失。
        """
        # 1. 尝试 Redis
        data = self._load_from_redis(book_id)
        if data:
            return data
        # 2. 兜底 JSON 文件
        from pathlib import Path
        from src.config import settings
        json_path = Path(settings.data_dir) / book_id / "cross_book_relations.json"
        if json_path.exists():
            try:
                return json.loads(json_path.read_text("utf-8"))
            except Exception as e:
                logger.warning("JSON 文件读取失败: %s", e)
        return None

    def _cleanup_redis(self, book_id: str) -> None:
        """清理 Redis 缓存。"""
        try:
            import redis
            from src.config.modules.redis import get_sync_redis
            r = get_sync_redis()
            r.delete(f"d2g:cross_analysis:{book_id}")
            r.delete(f"d2g:cross_decisions:{book_id}")
            logger.info("Redis 缓存已清理: %s", book_id)
        except Exception as e:
            logger.warning("Redis 清理失败: %s", e)


# ── 便捷函数 ─────────────────────────────────────────────────


async def run_phase5b_execute_decisions(
    book_id: str,
    neo4j_driver,
    analysis_result: dict | None = None,
) -> Phase5bOutcome:
    """Phase 5b 便捷入口。"""
    engine = CrossBookPhase5b(neo4j_driver=neo4j_driver)
    return await engine.run_phase5b(book_id, analysis_result)
