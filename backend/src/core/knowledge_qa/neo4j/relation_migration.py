"""关系迁移工具函数 — 跨书实体合并时迁移所有关联关系。

从 cross_book_resolver._merge_tx 提取的共用逻辑，
供 Phase 5b 和 cross_book_resolver 共同使用。

修复 BUG-2: 合并实体时 DETACH DELETE 直接丢弃关系，
改为先迁移再删除。
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def build_migration_cypher(
    new_name: str,
    new_book_id: str,
    existing_name: str,
    existing_book_id: str,
) -> list[tuple[str, dict]]:
    """构建实体合并时关系迁移的 Cypher 语句列表。

    迁移顺序（必须在 DETACH DELETE 之前执行）：
    1. 迁移普通入边
    2. 迁移普通出边
    3. 迁移 SAME_AS 入边
    4. 迁移 SAME_AS 出边
    5. 合并 book_ids
    6. 删除新节点

    返回 (cypher, params) 列表，调用方在事务中逐条执行。
    """
    params = {
        "new_name": new_name,
        "new_book_id": new_book_id,
        "existing_name": existing_name,
        "existing_book_id": existing_book_id,
    }

    return [
        # Step 1: 迁移普通入边（其他节点 → new）
        ("""
            MATCH (old {name: $existing_name})
            WHERE $existing_book_id IN coalesce(old.book_ids, [old.book_id])
            MATCH (new {name: $new_name})
            WHERE $new_book_id IN coalesce(new.book_ids, [new.book_id])
            MATCH (src)-[r]->(new)
            WHERE src <> old AND type(r) <> 'SAME_AS'
            CREATE (src)-[r2]->(old)
            SET r2 = properties(r)
            DELETE r
        """, params),

        # Step 2: 迁移普通出边（new → 其他节点）
        ("""
            MATCH (old {name: $existing_name})
            WHERE $existing_book_id IN coalesce(old.book_ids, [old.book_id])
            MATCH (new {name: $new_name})
            WHERE $new_book_id IN coalesce(new.book_ids, [new.book_id])
            MATCH (new)-[r]->(dst)
            WHERE dst <> old AND type(r) <> 'SAME_AS'
            CREATE (old)-[r2]->(dst)
            SET r2 = properties(r)
            DELETE r
        """, params),

        # Step 3: 迁移 SAME_AS 入边
        ("""
            MATCH (old {name: $existing_name})
            WHERE $existing_book_id IN coalesce(old.book_ids, [old.book_id])
            MATCH (new {name: $new_name})
            WHERE $new_book_id IN coalesce(new.book_ids, [new.book_id])
            MATCH (src)-[r:SAME_AS]->(new)
            WHERE src <> old
            CREATE (src)-[r2:SAME_AS]->(old)
            SET r2 = properties(r)
            DELETE r
        """, params),

        # Step 4: 迁移 SAME_AS 出边
        ("""
            MATCH (old {name: $existing_name})
            WHERE $existing_book_id IN coalesce(old.book_ids, [old.book_id])
            MATCH (new {name: $new_name})
            WHERE $new_book_id IN coalesce(new.book_ids, [new.book_id])
            MATCH (new)-[r:SAME_AS]->(dst)
            WHERE dst <> old
            CREATE (old)-[r2:SAME_AS]->(dst)
            SET r2 = properties(r)
            DELETE r
        """, params),

        # Step 5: 合并 book_ids
        ("""
            MATCH (old {name: $existing_name})
            WHERE $existing_book_id IN coalesce(old.book_ids, [old.book_id])
            MATCH (new {name: $new_name})
            WHERE $new_book_id IN coalesce(new.book_ids, [new.book_id])
            WITH old, new,
                 coalesce(old.book_ids, [old.book_id]) AS existing_book_ids,
                 coalesce(new.book_ids, [new.book_id]) AS new_book_ids
            SET old.book_ids = existing_book_ids +
                [bid IN new_book_ids WHERE NOT bid IN existing_book_ids]
        """, params),

        # Step 6: 删除新节点（关系已迁移，此时只残留无关系的 node）
        ("""
            MATCH (new {name: $new_name})
            WHERE $new_book_id IN coalesce(new.book_ids, [new.book_id])
            DETACH DELETE new
        """, params),
    ]
