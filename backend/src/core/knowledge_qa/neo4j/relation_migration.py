"""关系迁移工具函数 — 跨书实体合并时迁移所有关联关系。

从 cross_book_resolver._merge_tx 提取的共用逻辑，
供 Phase 5b 和 cross_book_resolver 共同使用。

修复 BUG-2: 合并实体时 DETACH DELETE 直接丢弃关系，
改为先迁移再删除。
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


async def build_migration_cypher_async(
    session,
    new_name: str,
    new_book_id: str,
    existing_name: str,
    existing_book_id: str,
) -> list[tuple[str, dict]]:
    """异步版：构建关系迁移 Cypher（修复 Cypher 语法错误）。

    先查询 new 节点的实际关系类型，再为每种类型构建带类型标注的
    迁移语句。解决原版 CREATE 缺少关系类型导致的 Neo4j 语法错误。
    """
    params = {
        "new_name": new_name,
        "new_book_id": new_book_id,
        "existing_name": existing_name,
        "existing_book_id": existing_book_id,
    }

    # 查询入边关系类型（排除 SAME_AS）
    result = await session.run(
        """
        MATCH (new {name: $new_name})
        WHERE $new_book_id IN coalesce(new.book_ids, [new.book_id])
        MATCH (src)-[r]->(new)
        WHERE type(r) <> 'SAME_AS'
        RETURN DISTINCT type(r) AS rel_type
        """,
        **params,
    )
    in_types = []
    async for record in result:
        in_types.append(record["rel_type"])

    # 查询出边关系类型（排除 SAME_AS）
    result = await session.run(
        """
        MATCH (new {name: $new_name})
        WHERE $new_book_id IN coalesce(new.book_ids, [new.book_id])
        MATCH (new)-[r]->(dst)
        WHERE type(r) <> 'SAME_AS'
        RETURN DISTINCT type(r) AS rel_type
        """,
        **params,
    )
    out_types = []
    async for record in result:
        out_types.append(record["rel_type"])

    stmts: list[tuple[str, dict]] = []

    # Step 1: 迁移普通入边（每种关系类型一条语句）
    for rel_type in in_types:
        stmts.append((
            """
            MATCH (old {name: $existing_name})
            WHERE $existing_book_id IN coalesce(old.book_ids, [old.book_id])
            MATCH (new {name: $new_name})
            WHERE $new_book_id IN coalesce(new.book_ids, [new.book_id])
            MATCH (src)-[r]->(new)
            WHERE src <> old AND type(r) = $rel_type
            CREATE (src)-[r2]->(old)
            SET r2 = properties(r)
            DELETE r
            """,
            {**params, "rel_type": rel_type},
        ))

    # Step 2: 迁移普通出边（每种关系类型一条语句）
    for rel_type in out_types:
        stmts.append((
            """
            MATCH (old {name: $existing_name})
            WHERE $existing_book_id IN coalesce(old.book_ids, [old.book_id])
            MATCH (new {name: $new_name})
            WHERE $new_book_id IN coalesce(new.book_ids, [new.book_id])
            MATCH (new)-[r]->(dst)
            WHERE dst <> old AND type(r) = $rel_type
            CREATE (old)-[r2]->(dst)
            SET r2 = properties(r)
            DELETE r
            """,
            {**params, "rel_type": rel_type},
        ))

    # Step 3: 迁移 SAME_AS 入边
    stmts.append((
        """
        MATCH (old {name: $existing_name})
        WHERE $existing_book_id IN coalesce(old.book_ids, [old.book_id])
        MATCH (new {name: $new_name})
        WHERE $new_book_id IN coalesce(new.book_ids, [new.book_id])
        MATCH (src)-[r:SAME_AS]->(new)
        WHERE src <> old
        CREATE (src)-[r2:SAME_AS]->(old)
        SET r2 = properties(r)
        DELETE r
        """, params,
    ))

    # Step 4: 迁移 SAME_AS 出边
    stmts.append((
        """
        MATCH (old {name: $existing_name})
        WHERE $existing_book_id IN coalesce(old.book_ids, [old.book_id])
        MATCH (new {name: $new_name})
        WHERE $new_book_id IN coalesce(new.book_ids, [new.book_id])
        MATCH (new)-[r:SAME_AS]->(dst)
        WHERE dst <> old
        CREATE (old)-[r2:SAME_AS]->(dst)
        SET r2 = properties(r)
        DELETE r
        """, params,
    ))

    # Step 5: 合并 book_ids
    stmts.append((
        """
        MATCH (old {name: $existing_name})
        WHERE $existing_book_id IN coalesce(old.book_ids, [old.book_id])
        MATCH (new {name: $new_name})
        WHERE $new_book_id IN coalesce(new.book_ids, [new.book_id])
        WITH old, new,
             coalesce(old.book_ids, [old.book_id]) AS existing_book_ids,
             coalesce(new.book_ids, [new.book_id]) AS new_book_ids
        SET old.book_ids = existing_book_ids +
            [bid IN new_book_ids WHERE NOT bid IN existing_book_ids]
        """, params,
    ))

    # Step 6: 删除新节点
    stmts.append((
        """
        MATCH (new {name: $new_name})
        WHERE $new_book_id IN coalesce(new.book_ids, [new.book_id])
        DETACH DELETE new
        """, params,
    ))

    return stmts


def build_migration_cypher_sync(
    tx,
    new_name: str,
    new_book_id: str,
    existing_name: str,
    existing_book_id: str,
) -> list[tuple[str, dict]]:
    """同步版：构建关系迁移 Cypher（修复 CREATE 缺少关系类型）。

    在事务内先查询 new 节点的实际关系类型，再为每种类型构建
    带类型标注的迁移语句。
    """
    params = {
        "new_name": new_name,
        "new_book_id": new_book_id,
        "existing_name": existing_name,
        "existing_book_id": existing_book_id,
    }

    # 查询入边关系类型（排除 SAME_AS）
    result = tx.run(
        """
        MATCH (new {name: $new_name})
        WHERE $new_book_id IN coalesce(new.book_ids, [new.book_id])
        MATCH (src)-[r]->(new)
        WHERE type(r) <> 'SAME_AS'
        RETURN DISTINCT type(r) AS rel_type
        """,
        **params,
    )
    in_types = [record["rel_type"] for record in result]

    # 查询出边关系类型（排除 SAME_AS）
    result = tx.run(
        """
        MATCH (new {name: $new_name})
        WHERE $new_book_id IN coalesce(new.book_ids, [new.book_id])
        MATCH (new)-[r]->(dst)
        WHERE type(r) <> 'SAME_AS'
        RETURN DISTINCT type(r) AS rel_type
        """,
        **params,
    )
    out_types = [record["rel_type"] for record in result]

    stmts: list[tuple[str, dict]] = []

    # Step 1: 迁移普通入边（每种关系类型一条语句）
    for rel_type in in_types:
        stmts.append((
            """
            MATCH (old {name: $existing_name})
            WHERE $existing_book_id IN coalesce(old.book_ids, [old.book_id])
            MATCH (new {name: $new_name})
            WHERE $new_book_id IN coalesce(new.book_ids, [new.book_id])
            MATCH (src)-[r]->(new)
            WHERE src <> old AND type(r) = $rel_type
            CREATE (src)-[r2]->(old)
            SET r2 = properties(r)
            DELETE r
            """,
            {**params, "rel_type": rel_type},
        ))

    # Step 2: 迁移普通出边（每种关系类型一条语句）
    for rel_type in out_types:
        stmts.append((
            """
            MATCH (old {name: $existing_name})
            WHERE $existing_book_id IN coalesce(old.book_ids, [old.book_id])
            MATCH (new {name: $new_name})
            WHERE $new_book_id IN coalesce(new.book_ids, [new.book_id])
            MATCH (new)-[r]->(dst)
            WHERE dst <> old AND type(r) = $rel_type
            CREATE (old)-[r2]->(dst)
            SET r2 = properties(r)
            DELETE r
            """,
            {**params, "rel_type": rel_type},
        ))

    # Step 3: 迁移 SAME_AS 入边
    stmts.append((
        """
        MATCH (old {name: $existing_name})
        WHERE $existing_book_id IN coalesce(old.book_ids, [old.book_id])
        MATCH (new {name: $new_name})
        WHERE $new_book_id IN coalesce(new.book_ids, [new.book_id])
        MATCH (src)-[r:SAME_AS]->(new)
        WHERE src <> old
        CREATE (src)-[r2:SAME_AS]->(old)
        SET r2 = properties(r)
        DELETE r
        """, params,
    ))

    # Step 4: 迁移 SAME_AS 出边
    stmts.append((
        """
        MATCH (old {name: $existing_name})
        WHERE $existing_book_id IN coalesce(old.book_ids, [old.book_id])
        MATCH (new {name: $new_name})
        WHERE $new_book_id IN coalesce(new.book_ids, [new.book_id])
        MATCH (new)-[r:SAME_AS]->(dst)
        WHERE dst <> old
        CREATE (old)-[r2:SAME_AS]->(dst)
        SET r2 = properties(r)
        DELETE r
        """, params,
    ))

    # Step 5: 合并 book_ids
    stmts.append((
        """
        MATCH (old {name: $existing_name})
        WHERE $existing_book_id IN coalesce(old.book_ids, [old.book_id])
        MATCH (new {name: $new_name})
        WHERE $new_book_id IN coalesce(new.book_ids, [new.book_id])
        WITH old, new,
             coalesce(old.book_ids, [old.book_id]) AS existing_book_ids,
             coalesce(new.book_ids, [new.book_id]) AS new_book_ids
        SET old.book_ids = existing_book_ids +
            [bid IN new_book_ids WHERE NOT bid IN existing_book_ids]
        """, params,
    ))

    # Step 6: 删除新节点
    stmts.append((
        """
        MATCH (new {name: $new_name})
        WHERE $new_book_id IN coalesce(new.book_ids, [new.book_id])
        DETACH DELETE new
        """, params,
    ))

    return stmts
