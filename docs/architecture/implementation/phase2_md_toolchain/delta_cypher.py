"""Delta Cypher 生成器 — 仅生成变更部分的 Cypher 语句。

放置位置: backend/src/core/knowledge_qa/neo4j/delta_cypher.py
"""

from __future__ import annotations

import logging
from .md_diff_analyzer import DiffResult, ChangeType

logger = logging.getLogger(__name__)


def generate_delta_cypher(diff: DiffResult) -> list[dict]:
    """根据 Diff 结果生成增量 Cypher 语句。

    仅处理 ADDED / MODIFIED / DELETED，UNCHANGED 不生成语句。

    Args:
        diff: Diff 结果

    Returns:
        [{query, params, description}]
    """
    statements = []

    for d in diff.entity_diffs + diff.claim_diffs + diff.prescription_diffs:
        if d.change_type == ChangeType.ADDED:
            statements.extend(_cypher_for_added(d.new_data, diff.book_id))
        elif d.change_type == ChangeType.MODIFIED:
            statements.extend(_cypher_for_modified(d.new_data, d.changed_fields, diff.book_id))
        elif d.change_type == ChangeType.DELETED:
            statements.extend(_cypher_for_deleted(d.old_data, diff.book_id))

    logger.info("Delta Cypher: %d 条语句", len(statements))
    return statements


def _cypher_for_added(entity: dict, book_id: str) -> list[dict]:
    """新增实体的 Cypher。"""
    name = entity.get("name", entity.get("exercise", ""))
    etype = entity.get("entity_type", entity.get("type", "AutoEntity"))
    label = etype if etype in ("Problem", "Solution", "BrainRegion", "Risk") else "AutoEntity"

    return [{
        "query": f"MERGE (n:{label} {{name: $name, book_id: $book_id}}) SET n += $props",
        "params": {"name": name, "book_id": book_id, "props": entity},
        "description": f"ADD {label} {name}",
    }]


def _cypher_for_modified(entity: dict, fields: list[str], book_id: str) -> list[dict]:
    """修改实体的 Cypher — 仅更新变更字段。"""
    name = entity.get("name", entity.get("exercise", ""))
    etype = entity.get("entity_type", entity.get("type", "AutoEntity"))
    label = etype if etype in ("Problem", "Solution", "BrainRegion", "Risk") else "AutoEntity"

    set_clauses = ", ".join(f"n.{f} = ${f}" for f in fields)
    params = {"name": name, "book_id": book_id}
    for f in fields:
        params[f] = entity.get(f)

    return [{
        "query": f"MATCH (n:{label} {{name: $name, book_id: $book_id}}) SET {set_clauses}",
        "params": params,
        "description": f"MODIFY {label} {name} [{', '.join(fields)}]",
    }]


def _cypher_for_deleted(entity: dict, book_id: str) -> list[dict]:
    """删除实体的 Cypher — 仅断开关系，不删除节点（安全策略）。"""
    name = entity.get("name", entity.get("exercise", ""))
    etype = entity.get("entity_type", entity.get("type", "AutoEntity"))
    label = etype if etype in ("Problem", "Solution", "BrainRegion", "Risk") else "AutoEntity"

    return [{
        "query": f"""
            MATCH (n:{label} {{name: $name, book_id: $book_id}})
            SET n.curation_status = 'deleted', n.deleted_at = datetime()
        """,
        "params": {"name": name, "book_id": book_id},
        "description": f"SOFT DELETE {label} {name}",
    }]
