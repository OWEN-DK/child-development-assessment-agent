"""自定义知识 Repository — MySQL 索引 CRUD + Neo4j CustomRule 双写

放置位置: backend/src/repository/custom_knowledge_repository.py
依赖:
  - SQLAlchemy ≥ 2.0 (async)
  - Neo4j Python Driver ≥ 5.0
  - backend/src/core/database.py (Base, async_session_factory)
  - backend/src/core/knowledge_qa/neo4j/driver.py (get_neo4j_driver)
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import Column, Integer, String, JSON, Boolean, DateTime, func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from src.core.database import Base

logger = logging.getLogger(__name__)


# ── MySQL ORM（轻量，仅索引字段） ──


class CustomKnowledgeIndex(Base):
    """MySQL 辅助索引表，仅用于快速匹配。Neo4j CustomRule 是真相源。"""
    __tablename__ = "custom_knowledge_index"
    rule_id = Column(String(32), primary_key=True, comment="对应 Neo4j CustomRule.rule_id")
    keywords = Column(JSON, nullable=True, comment="精确匹配关键词列表")
    trigger_patterns = Column(JSON, nullable=True, comment="正则触发模式列表")
    embedding = Column(JSON, nullable=True, comment="语义向量 (1536 维)")
    priority = Column(Integer, nullable=False, default=100)
    enabled = Column(Boolean, nullable=False, default=True)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    __table_args__ = ({"extend_existing": True},)


# ── Repository ──


class CustomKnowledgeRepository:
    """双写 Repository: Neo4j (真相源) + MySQL (索引)

    设计要点:
    - Neo4j 存储 CustomRule 节点的完整数据（title, content, category, ...）
    - MySQL 仅存储匹配所需的索引字段（keywords, trigger_patterns, embedding）
    - 所有写操作先写 Neo4j 再写 MySQL，失败时告警但不阻塞
    - 所有读操作从对应最优数据源读取
    """

    def __init__(self, db_session_factory: async_sessionmaker, neo4j_driver=None):
        self._sf = db_session_factory
        self._neo4j = neo4j_driver

    # ════════════════════════════════════════════════════════════
    # MySQL 索引查询（三通道匹配用）
    # ════════════════════════════════════════════════════════════

    async def get_all_enabled(self, limit: int = 500) -> List[CustomKnowledgeIndex]:
        """获取所有启用的索引条目（按 priority DESC）"""
        async with self._sf() as session:
            r = await session.execute(
                select(CustomKnowledgeIndex)
                .where(CustomKnowledgeIndex.enabled == True)  # noqa: E712
                .order_by(CustomKnowledgeIndex.priority.desc())
                .limit(limit)
            )
            return list(r.scalars().all())

    async def keyword_match(self, question: str) -> List[CustomKnowledgeIndex]:
        """通道 1: 关键词精确匹配（大小写不敏感）"""
        items = await self.get_all_enabled()
        q = question.lower()
        matched = []
        for item in items:
            for kw in (item.keywords or []):
                if kw and kw.lower() in q:
                    matched.append(item)
                    break
        return matched

    async def pattern_match(self, question: str) -> List[CustomKnowledgeIndex]:
        """通道 2: 正则模式匹配"""
        items = await self.get_all_enabled()
        matched = []
        for item in items:
            for pat in (item.trigger_patterns or []):
                if not pat:
                    continue
                try:
                    if re.search(pat, question, re.IGNORECASE):
                        matched.append(item)
                        break
                except re.error:
                    logger.warning(f"无效正则 '{pat}' (rule_id={item.rule_id})")
        return matched

    async def get_by_rule_id(self, rule_id: str) -> Optional[CustomKnowledgeIndex]:
        async with self._sf() as session:
            r = await session.execute(
                select(CustomKnowledgeIndex).where(CustomKnowledgeIndex.rule_id == rule_id)
            )
            return r.scalar_one_or_none()

    # ════════════════════════════════════════════════════════════
    # MySQL 写入
    # ════════════════════════════════════════════════════════════

    async def upsert_index(self, rule_id: str, data: Dict[str, Any]) -> None:
        """创建或更新 MySQL 索引条目"""
        async with self._sf() as session:
            existing = await session.execute(
                select(CustomKnowledgeIndex).where(CustomKnowledgeIndex.rule_id == rule_id)
            )
            obj = existing.scalar_one_or_none()
            if obj:
                for k, v in data.items():
                    setattr(obj, k, v)
            else:
                session.add(CustomKnowledgeIndex(rule_id=rule_id, **data))
            await session.commit()

    async def delete_index(self, rule_id: str) -> None:
        async with self._sf() as session:
            await session.execute(
                CustomKnowledgeIndex.__table__.delete().where(
                    CustomKnowledgeIndex.rule_id == rule_id
                )
            )
            await session.commit()

    async def update_embedding(self, rule_id: str, embedding: list) -> None:
        await self.upsert_index(rule_id, {"embedding": embedding})

    # ════════════════════════════════════════════════════════════
    # Neo4j 读取
    # ════════════════════════════════════════════════════════════

    async def get_custom_rule(self, rule_id: str) -> Optional[dict]:
        """从 Neo4j 取 CustomRule 完整节点"""
        if not self._neo4j:
            return None
        try:
            with self._neo4j.session() as s:
                r = s.run(
                    "MATCH (r:CustomRule {rule_id: $rid}) RETURN properties(r) AS props",
                    rid=rule_id,
                )
                rec = r.single()
                return dict(rec["props"]) if rec else None
        except Exception as e:
            logger.warning(f"Neo4j get_custom_rule failed: {e}")
            return None

    async def get_custom_rule_relations(self, rule_id: str) -> List[dict]:
        """从 Neo4j 取 CustomRule 的所有出向关系"""
        if not self._neo4j:
            return []
        try:
            with self._neo4j.session() as s:
                r = s.run(
                    "MATCH (r:CustomRule {rule_id: $rid})-[rel]->(t) "
                    "RETURN type(rel) AS rel_type, t.name AS target_name, "
                    "       labels(t) AS target_labels, properties(rel) AS rel_props",
                    rid=rule_id,
                )
                return [dict(rec) for rec in r]
        except Exception as e:
            logger.warning(f"Neo4j get_custom_rule_relations failed: {e}")
            return []

    async def increment_hit(self, rule_id: str) -> None:
        """命中计数递增（仅 Neo4j）"""
        if not self._neo4j:
            return
        try:
            with self._neo4j.session() as s:
                s.run(
                    "MATCH (r:CustomRule {rule_id: $rid}) "
                    "SET r.match_count = coalesce(r.match_count, 0) + 1, "
                    "    r.last_matched_at = datetime()",
                    rid=rule_id,
                )
        except Exception as e:
            logger.debug(f"hit count update failed: {e}")

    # ════════════════════════════════════════════════════════════
    # Neo4j 写入
    # ════════════════════════════════════════════════════════════

    async def create_custom_rule(self, data: Dict[str, Any]) -> str:
        """在 Neo4j 创建 CustomRule 节点，返回 rule_id"""
        if not self._neo4j:
            raise RuntimeError("Neo4j not available")
        rule_id = data["rule_id"]
        with self._neo4j.session() as s:
            s.run(
                "MERGE (r:CustomRule {rule_id: $rid}) "
                "SET r.title = $title, r.content = $content, "
                "    r.category = $category, r.priority = $priority, "
                "    r.enabled = true, r.source = $source, "
                "    r.match_count = 0, r.created_at = datetime()",
                rid=rule_id,
                title=data["title"],
                content=data["content"],
                category=data.get("category", "general"),
                priority=data.get("priority", 100),
                source=data.get("source", ""),
            )
        return rule_id

    async def delete_custom_rule(self, rule_id: str) -> None:
        if not self._neo4j:
            return
        with self._neo4j.session() as s:
            s.run("MATCH (r:CustomRule {rule_id: $rid}) DETACH DELETE r", rid=rule_id)

    async def create_relation(
        self, rule_id: str, target_name: str, target_type: str,
        rel_type: str, props: dict = None,
    ) -> None:
        """创建 CustomRule → 实体的关系"""
        if not self._neo4j:
            return
        with self._neo4j.session() as s:
            s.run(
                f"MATCH (r:CustomRule {{rule_id: $rid}}) "
                f"MATCH (t:{target_type} {{name: $tname}}) "
                f"MERGE (r)-[rel:{rel_type}]->(t) "
                f"SET rel += $props",
                rid=rule_id, tname=target_name, props=props or {},
            )
