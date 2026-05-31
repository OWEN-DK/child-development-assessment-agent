"""Phase 4: 入库 Neo4j（含 Staging 模式，§07-16.1）。

放置位置: backend/src/core/knowledge_qa/d2g/graph_committer.py

Staging 模式流程:
  1. 所有实体/关系先写临时 label `:D2G_Staging`，带 `extraction_version: "d2g"` 标签
  2. 全部写入成功后，在同一事务中: 删除旧节点 + 将 staging 节点提升为正式 label
  3. 失败时 staging 节点保留但隔离，不影响旧数据，可手动清理或重试
"""

from __future__ import annotations

import logging

from .master_graph import MasterGraph
from src.core.knowledge_qa.neo4j.schema import KNOWN_ENTITY_TYPES

logger = logging.getLogger(__name__)

STAGING_LABEL = "D2G_Staging"
EXTRACTION_VERSION = "d2g"


async def commit_to_neo4j(
    master: MasterGraph,
    neo4j_session,
    dry_run: bool = False,
    use_staging: bool = True,
) -> bool:
    """将主图写入 Neo4j。

    支持两种模式:
    - use_staging=True (推荐): 先写 Staging → 验证通过 → 提升为正式 label
    - use_staging=False: 直接写正式 label（旧行为兼容）

    Args:
        master: 主图
        neo4j_session: Neo4j session
        dry_run: 仅打印不执行
        use_staging: 是否使用 Staging 模式

    Returns:
        是否成功
    """
    if use_staging:
        return await _commit_with_staging(master, neo4j_session, dry_run)

    statements = _generate_cypher(master)
    logger.info("生成 %d 条 Cypher 语句（直接模式）", len(statements))

    if dry_run:
        for stmt in statements:
            logger.info("[DRY RUN] %s", stmt["description"])
        return True

    try:
        tx = await neo4j_session.begin_transaction()
        try:
            for stmt in statements:
                await tx.run(stmt["query"], **stmt["params"])
            await tx.commit()
        except Exception:
            await tx.rollback()
            raise
        logger.info("Neo4j 入库成功: %d 条语句", len(statements))
        return True
    except Exception as e:
        logger.error("Neo4j 入库失败: %s", e)
        return False


# ── Staging 模式实现 (§07-16.1) ──────────────────────────────


async def _commit_with_staging(
    master: MasterGraph,
    neo4j_session,
    dry_run: bool = False,
) -> bool:
    """Staging 模式入库: 先写临时 label，成功后提升。

    分两阶段:
      Phase A: 所有节点/关系写入 :D2G_Staging 临时 label
      Phase B: 在同一事务中删除旧节点 + 将 staging 节点提升为正式 label
    """
    book_id = master.book_id

    # ── Phase A: 写入 Staging ──
    staging_statements = _generate_staging_cypher(master)
    logger.info("Phase A: 生成 %d 条 Staging Cypher 语句", len(staging_statements))

    if dry_run:
        for stmt in staging_statements:
            logger.info("[DRY RUN] %s", stmt["description"])
        return True

    try:
        tx = await neo4j_session.begin_transaction()
        try:
            for stmt in staging_statements:
                await tx.run(stmt["query"], **stmt["params"])
            await tx.commit()
        except Exception:
            await tx.rollback()
            raise
        logger.info("Phase A 完成: Staging 节点已写入")
    except Exception as e:
        logger.error("Phase A Staging 写入失败: %s", e)
        return False

    # ── Phase B: 提升 Staging → 正式 ──
    try:
        tx = await neo4j_session.begin_transaction()
        try:
            await _promote_staging(book_id, tx)
            await tx.commit()
        except Exception:
            await tx.rollback()
            raise
        logger.info("Phase B 完成: Staging → 正式 label 提升成功")
        return True
    except Exception as e:
        logger.error("Phase B 提升失败（Staging 节点保留，旧数据不受影响）: %s", e)
        return False


def _generate_staging_cypher(master: MasterGraph) -> list[dict]:
    """生成 Staging 模式的 Cypher 语句。

    所有节点创建时打上 :D2G_Staging + extraction_version 标签。
    """
    statements = []
    book_id = master.book_id

    # Book 节点（Book 不属于 D2G 实体，不写 Staging）
    statements.append({
        "query": "MERGE (b:Book {book_id: $book_id}) SET b.title = $title",
        "params": {"book_id": book_id, "title": master.book_title},
        "description": f"MERGE Book {master.book_title}",
    })

    # Entity 节点 → Staging
    for node in master.graph.nodes:
        data = master.graph.nodes[node]
        entity_type = data.get("entity_type", "AutoEntity")
        real_label = entity_type if entity_type in KNOWN_ENTITY_TYPES else "AutoEntity"
        description = data.get("description", "")
        name_norm = node.strip().lower()

        # 写入时用双 label: real_label + D2G_Staging
        # 这样后续提升时只需 REMOVE :D2G_Staging
        statements.append({
            "query": (
                f"MERGE (n:{real_label}:{STAGING_LABEL} {{name_normalized: $name_norm, book_id: $book_id}}) "
                f"SET n.name = $name, n.description = $desc, "
                f"n.extraction_version = $ext_ver, "
                f"n.book_ids = coalesce(n.book_ids, []) + [$book_id]"
            ),
            "params": {
                "name": node, "name_norm": name_norm, "book_id": book_id,
                "desc": description, "ext_ver": EXTRACTION_VERSION,
            },
            "description": f"MERGE {real_label}:{STAGING_LABEL} {node}",
        })

        # Book → Entity 关系
        statements.append({
            "query": (
                f"MATCH (b:Book {{book_id: $book_id}}) "
                f"MATCH (n:{real_label}:{STAGING_LABEL} {{name_normalized: $name_norm, book_id: $book_id}}) "
                f"MERGE (b)-[:CONTAINS_ENTITY]->(n)"
            ),
            "params": {"book_id": book_id, "name_norm": name_norm},
            "description": f"LINK Book → {real_label} {node}",
        })

    # 边（关系）
    for src, tgt, data in master.graph.edges(data=True):
        rel_type = data.get("relation_type", "RELATES_TO")
        rel_type = rel_type.value if hasattr(rel_type, "value") else str(rel_type).upper().replace(" ", "_").replace("-", "_")
        evidence = data.get("evidence", "")

        statements.append({
            "query": (
                f"MATCH (a {{name_normalized: $src_norm, book_id: $book_id}}) "
                f"MATCH (b {{name_normalized: $tgt_norm, book_id: $book_id}}) "
                f"MERGE (a)-[r:{rel_type}]->(b) "
                f"SET r.evidence = $evidence"
            ),
            "params": {
                "book_id": book_id, "src_norm": src.strip().lower(),
                "tgt_norm": tgt.strip().lower(), "evidence": evidence,
            },
            "description": f"LINK {src} → {rel_type} → {tgt}",
        })

    return statements


async def _promote_staging(book_id: str, tx) -> None:
    """将 Staging 节点提升为正式节点。

    在同一事务中执行:
      1. 查找旧数据（同 book_id 的非 Staging 节点+关系），删除
      2. 将 Staging 节点的 :D2G_Staging label 移除
      3. 清理 extraction_version 属性
    """
    # Step 1: 删除同书旧节点及其关系（不包括 Staging 节点）
    await tx.run("""
        MATCH (n {book_id: $book_id})
        WHERE NOT n:D2G_Staging
        DETACH DELETE n
    """, book_id=book_id)
    logger.info("已删除 book_id=%s 的旧节点", book_id)

    # Step 2: 移除 Staging label，清理临时属性
    await tx.run("""
        MATCH (n:D2G_Staging {book_id: $book_id})
        REMOVE n:D2G_Staging
        REMOVE n.extraction_version
    """, book_id=book_id)
    logger.info("Staging 节点已提升为正式 label: book_id=%s", book_id)


async def rollback_staging(book_id: str, neo4j_session) -> int:
    """回滚指定书籍的 Staging 节点（用于失败后清理）。

    Returns:
        删除的节点数量
    """
    try:
        tx = await neo4j_session.begin_transaction()
        try:
            result = await tx.run("""
                MATCH (n:D2G_Staging {book_id: $book_id})
                DETACH DELETE n
                RETURN count(n) AS deleted
            """, book_id=book_id)
            record = await result.single()
            count = record["deleted"] if record else 0
            await tx.commit()
        except Exception:
            await tx.rollback()
            raise
        logger.info("Staging 回滚: 删除 %d 个节点 (book_id=%s)", count, book_id)
        return count
    except Exception as e:
        logger.error("Staging 回滚失败: %s", e)
        return 0


async def list_staging_books(neo4j_session) -> list[dict]:
    """列出所有处于 Staging 状态的书籍（用于运维排查）。"""
    try:
        result = await neo4j_session.run("""
            MATCH (n:D2G_Staging)
            WITH DISTINCT n.book_id AS book_id, n.extraction_version AS ver
            OPTIONAL MATCH (n2:D2G_Staging {book_id: book_id})
            RETURN book_id, ver, count(n2) AS node_count
        """)
        records = await result.data()
        return records
    except Exception as e:
        logger.error("查询 Staging 书籍失败: %s", e)
        return []


# ── 旧版直接模式（兼容） ─────────────────────────────────────


def _generate_cypher(master: MasterGraph) -> list[dict]:
    """从主图生成 Cypher MERGE 语句（直接模式，不含 Staging）。"""
    statements = []
    book_id = master.book_id

    # Book 节点
    statements.append({
        "query": "MERGE (b:Book {book_id: $book_id}) SET b.title = $title",
        "params": {"book_id": book_id, "title": master.book_title},
        "description": f"MERGE Book {master.book_title}",
    })

    # Entity 节点
    for node in master.graph.nodes:
        data = master.graph.nodes[node]
        entity_type = data.get("entity_type", "AutoEntity")
        label = entity_type if entity_type in KNOWN_ENTITY_TYPES else "AutoEntity"
        description = data.get("description", "")

        name_norm = node.strip().lower()
        statements.append({
            "query": (
                f"MERGE (n:{label} {{name_normalized: $name_norm, book_id: $book_id}}) "
                f"SET n.name = $name, n.description = $desc, "
                f"n.book_ids = coalesce(n.book_ids, []) + [$book_id]"
            ),
            "params": {"name": node, "name_norm": name_norm, "book_id": book_id, "desc": description},
            "description": f"MERGE {label} {node}",
        })

        # Book → Entity 关系
        statements.append({
            "query": (
                f"MATCH (b:Book {{book_id: $book_id}}) "
                f"MATCH (n:{label} {{name_normalized: $name_norm, book_id: $book_id}}) "
                f"MERGE (b)-[:CONTAINS_ENTITY]->(n)"
            ),
            "params": {"book_id": book_id, "name_norm": name_norm},
            "description": f"LINK Book → {label} {node}",
        })

    # 边（关系）
    for src, tgt, data in master.graph.edges(data=True):
        rel_type = data.get("relation_type", "RELATES_TO")
        rel_type = rel_type.value if hasattr(rel_type, "value") else str(rel_type).upper().replace(" ", "_").replace("-", "_")
        evidence = data.get("evidence", "")

        statements.append({
            "query": (
                f"MATCH (a {{name_normalized: $src_norm, book_id: $book_id}}) "
                f"MATCH (b {{name_normalized: $tgt_norm, book_id: $book_id}}) "
                f"MERGE (a)-[r:{rel_type}]->(b) "
                f"SET r.evidence = $evidence"
            ),
            "params": {"book_id": book_id, "src_norm": src.strip().lower(), "tgt_norm": tgt.strip().lower(), "evidence": evidence},
            "description": f"LINK {src} → {rel_type} → {tgt}",
        })

    return statements
