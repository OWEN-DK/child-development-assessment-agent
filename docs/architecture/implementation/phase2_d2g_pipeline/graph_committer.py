"""Phase 4: 入库 Neo4j。

放置位置: backend/src/core/knowledge_qa/neo4j/graph_committer.py
"""

from __future__ import annotations

import logging

from .master_graph import MasterGraph
from .schema import KNOWN_ENTITY_TYPES

logger = logging.getLogger(__name__)


async def commit_to_neo4j(
    master: MasterGraph,
    neo4j_session,
    dry_run: bool = False,
) -> bool:
    """将主图写入 Neo4j。

    Args:
        master: 主图
        neo4j_session: Neo4j session
        dry_run: 仅打印不执行

    Returns:
        是否成功
    """
    statements = _generate_cypher(master)

    logger.info("生成 %d 条 Cypher 语句", len(statements))

    if dry_run:
        for stmt in statements:
            logger.info("[DRY RUN] %s", stmt["description"])
            logger.info("  Query: %s", stmt["query"][:100])
        return True

    try:
        async with neo4j_session.begin_transaction() as tx:
            for stmt in statements:
                tx.run(stmt["query"], **stmt["params"])
        logger.info("Neo4j 入库成功: %d 条语句", len(statements))
        return True
    except Exception as e:
        logger.error("Neo4j 入库失败: %s", e)
        return False


def _generate_cypher(master: MasterGraph) -> list[dict]:
    """从主图生成 Cypher MERGE 语句。"""
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

        statements.append({
            "query": (
                f"MERGE (n:{label} {{name: $name, book_id: $book_id}}) "
                f"SET n.description = $desc"
            ),
            "params": {"name": node, "book_id": book_id, "desc": description},
            "description": f"MERGE {label} {node}",
        })

        # Book → Entity 关系
        statements.append({
            "query": (
                f"MATCH (b:Book {{book_id: $book_id}}) "
                f"MATCH (n:{label} {{name: $name, book_id: $book_id}}) "
                f"MERGE (b)-[:CONTAINS_ENTITY]->(n)"
            ),
            "params": {"book_id": book_id, "name": node},
            "description": f"LINK Book → {label} {node}",
        })

    # 边（关系）
    for src, tgt, data in master.graph.edges(data=True):
        rel_type = data.get("relation_type", "RELATES_TO")
        evidence = data.get("evidence", "")

        statements.append({
            "query": (
                f"MATCH (a {{name: $src, book_id: $book_id}}) "
                f"MATCH (b {{name: $tgt, book_id: $book_id}}) "
                f"MERGE (a)-[r:{rel_type}]->(b) "
                f"SET r.evidence = $evidence"
            ),
            "params": {"book_id": book_id, "src": src, "tgt": tgt, "evidence": evidence},
            "description": f"LINK {src} → {rel_type} → {tgt}",
        })

    return statements
