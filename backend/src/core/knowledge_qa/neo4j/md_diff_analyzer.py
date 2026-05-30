"""结构化 Diff 引擎 — 对比两个版本的 MD，生成变更列表。

放置位置: backend/src/core/knowledge_qa/neo4j/md_diff_analyzer.py
对标项目已有的 PromptImpactAnalyzer 模式。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class ChangeType(Enum):
    ADDED = "added"
    MODIFIED = "modified"
    DELETED = "deleted"
    UNCHANGED = "unchanged"


@dataclass
class EntityDiff:
    """单个实体的变更。"""
    entity_key: str         # "entity_type::name"
    change_type: ChangeType
    old_data: dict = field(default_factory=dict)
    new_data: dict = field(default_factory=dict)
    changed_fields: list[str] = field(default_factory=list)


@dataclass
class DiffResult:
    """MD 版本 Diff 结果。"""
    old_version: int
    new_version: int
    book_id: str
    entity_diffs: list[EntityDiff] = field(default_factory=list)
    claim_diffs: list[EntityDiff] = field(default_factory=list)
    prescription_diffs: list[EntityDiff] = field(default_factory=list)

    @property
    def summary(self) -> dict:
        counts = {"added": 0, "modified": 0, "deleted": 0, "unchanged": 0}
        for diff in self.entity_diffs + self.claim_diffs + self.prescription_diffs:
            counts[diff.change_type.value] += 1
        return counts


class MDDiffAnalyzer:
    """MD 版本 Diff 分析器。

    使用方式:
        analyzer = MDDiffAnalyzer()
        result = analyzer.analyze(old_parsed, new_parsed)
    """

    def analyze(self, old_data: dict, new_data: dict) -> DiffResult:
        """对比两个版本的解析数据，生成 Diff。

        Args:
            old_data: 旧版解析结果 {entities: [...], claims: [...], prescriptions: [...]}
            new_data: 新版解析结果

        Returns:
            DiffResult
        """
        result = DiffResult(
            old_version=old_data.get("version", 0),
            new_version=new_data.get("version", 1),
            book_id=new_data.get("book_id", ""),
        )

        result.entity_diffs = self._diff_entities(
            old_data.get("entities", []), new_data.get("entities", [])
        )
        result.claim_diffs = self._diff_entities(
            old_data.get("claims", []), new_data.get("claims", [])
        )
        result.prescription_diffs = self._diff_entities(
            old_data.get("prescriptions", []), new_data.get("prescriptions", [])
        )

        logger.info("Diff 完成: %s", result.summary)
        return result

    def _diff_entities(self, old_list: list[dict], new_list: list[dict]) -> list[EntityDiff]:
        """对比两个实体列表。"""
        old_map = {self._key(e): e for e in old_list}
        new_map = {self._key(e): e for e in new_list}

        diffs = []

        # 已删除
        for key in old_map:
            if key not in new_map:
                diffs.append(EntityDiff(
                    entity_key=key, change_type=ChangeType.DELETED,
                    old_data=old_map[key],
                ))

        # 新增 + 修改
        for key in new_map:
            if key not in old_map:
                diffs.append(EntityDiff(
                    entity_key=key, change_type=ChangeType.ADDED,
                    new_data=new_map[key],
                ))
            else:
                changed = self._find_changed_fields(old_map[key], new_map[key])
                if changed:
                    diffs.append(EntityDiff(
                        entity_key=key, change_type=ChangeType.MODIFIED,
                        old_data=old_map[key], new_data=new_map[key],
                        changed_fields=changed,
                    ))
                else:
                    diffs.append(EntityDiff(
                        entity_key=key, change_type=ChangeType.UNCHANGED,
                    ))

        return diffs

    @staticmethod
    def _key(entity: dict) -> str:
        """生成实体唯一键。"""
        etype = entity.get("entity_type", entity.get("type", ""))
        name = entity.get("name", entity.get("exercise", ""))
        return f"{etype}::{name}"

    @staticmethod
    def _find_changed_fields(old: dict, new: dict) -> list[str]:
        """找出变更的字段。"""
        all_keys = set(old.keys()) | set(new.keys())
        changed = []
        for k in all_keys:
            if old.get(k) != new.get(k):
                changed.append(k)
        return changed
