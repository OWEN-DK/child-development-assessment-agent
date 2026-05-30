"""同义词注册表 — 处理实体名称消歧和标准化。

放置位置: backend/src/core/knowledge_qa/neo4j/synonym_registry.py
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class SynonymGroup:
    """一组同义词。"""
    canonical: str          # 标准名称
    aliases: list[str]      # 别名列表
    entity_type: str = ""   # 实体类型


class SynonymRegistry:
    """同义词注册表 — 管理实体名称的标准形式和别名。"""

    def __init__(self):
        self._groups: list[SynonymGroup] = []
        self._alias_map: dict[str, str] = {}  # alias → canonical

    def register(self, canonical: str, aliases: list[str], entity_type: str = ""):
        """注册一组同义词。"""
        group = SynonymGroup(canonical=canonical, aliases=aliases, entity_type=entity_type)
        self._groups.append(group)
        self._alias_map[canonical] = canonical
        for alias in aliases:
            self._alias_map[alias] = canonical
        logger.debug("注册同义词: %s → %s", aliases, canonical)

    def resolve(self, name: str) -> str:
        """将名称解析为标准形式。找不到则返回原名。"""
        return self._alias_map.get(name, name)

    def get_aliases(self, canonical: str) -> list[str]:
        """获取标准名称的所有别名。"""
        for group in self._groups:
            if group.canonical == canonical:
                return group.aliases
        return []

    @classmethod
    def from_neo4j(cls, session) -> SynonymRegistry:
        """从 Neo4j 加载同义词注册表。"""
        registry = cls()
        result = session.run("""
            MATCH (ae:AutoEntity)
            WHERE ae.aliases IS NOT NULL AND size(ae.aliases) > 0
            RETURN ae.name AS name, ae.aliases AS aliases, ae.entity_type AS type
        """)
        for record in result:
            registry.register(record["name"], record["aliases"], record.get("type", ""))
        logger.info("从 Neo4j 加载 %d 组同义词", len(registry._groups))
        return registry
