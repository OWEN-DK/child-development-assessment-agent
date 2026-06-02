"""跨书数据清理 — 删除书籍时彻底清理所有跨书相关数据。

放置位置: backend/src/core/knowledge_qa/neo4j/cross_book_cleanup.py
依赖:
  - Neo4j 驱动
  - Redis 客户端

设计文档: docs/architecture/13-跨书知识融合方案-v2.md §7
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Protocol

logger = logging.getLogger(__name__)


# ── Protocol ─────────────────────────────────────────────────


class Neo4jDriver(Protocol):
    def session(self) -> Any: ...


# ── 核心清理器 ───────────────────────────────────────────────


class CrossBookCleanup:
    """跨书数据清理器。

    删除一本书时，彻底清理所有跨书相关数据：
    1. Neo4j 中的实体节点和关系边
    2. Redis 中的分析缓存
    3. JSON 文件
    """

    def __init__(self, neo4j_driver: Neo4jDriver):
        self._neo4j = neo4j_driver

    async def cleanup_book(self, book_id: str) -> dict:
        """清理指定书籍的所有跨书数据。

        Args:
            book_id: 要删除的书籍 ID

        Returns:
            清理结果统计
        """
        result = {
            "book_id": book_id,
            "neo4j_deleted_nodes": 0,
            "neo4j_deleted_relations": 0,
            "redis_cleaned": False,
            "files_cleaned": False,
            "errors": [],
        }

        try:
            # Step 1: 清理 Neo4j
            neo4j_result = await self._cleanup_neo4j(book_id)
            result["neo4j_deleted_nodes"] = neo4j_result.get("deleted_nodes", 0)
            result["neo4j_deleted_relations"] = neo4j_result.get("deleted_relations", 0)

            # Step 2: 清理 Redis
            redis_cleaned = self._cleanup_redis(book_id)
            result["redis_cleaned"] = redis_cleaned

            # Step 3: 清理 JSON 文件
            files_cleaned = self._cleanup_files(book_id)
            result["files_cleaned"] = files_cleaned

            logger.info(
                "跨书数据清理完成: book_id=%s, 节点=%d, 关系=%d",
                book_id, result["neo4j_deleted_nodes"], result["neo4j_deleted_relations"],
            )

        except Exception as e:
            logger.error("跨书数据清理失败: %s", e, exc_info=True)
            result["errors"].append(str(e))

        return result

    async def _cleanup_neo4j(self, book_id: str) -> dict:
        """清理 Neo4j 中的跨书数据。

        按照 §7.4 的 5 步清理逻辑：
        1. 删除该书独有的实体节点
        2. 对于合并实体，从 book_ids 中移除该书
        3. 删除该书相关的跨书关系边
        4. 清理 MergeLog 节点
        5. 删除该书的 Book 节点
        """
        deleted_nodes = 0
        deleted_relations = 0

        async with self._neo4j.session() as session:
            # Step 1: 删除该书独有的实体节点
            result = await session.run(
                """
                MATCH (n)
                WHERE $book_id IN coalesce(n.book_ids, [n.book_id])
                  AND size(coalesce(n.book_ids, [n.book_id])) = 1
                  AND NOT n:Book
                  AND NOT n:MergeLog
                DETACH DELETE n
                RETURN count(n) AS deleted
                """,
                book_id=book_id,
            )
            record = await result.single()
            deleted_nodes += record["deleted"] if record else 0

            # Step 2: 对于合并实体，从 book_ids 中移除该书
            await session.run(
                """
                MATCH (n)
                WHERE $book_id IN coalesce(n.book_ids, [n.book_id])
                  AND size(coalesce(n.book_ids, [n.book_id])) > 1
                SET n.book_ids = [bid IN coalesce(n.book_ids, [n.book_id]) WHERE bid <> $book_id]
                """,
                book_id=book_id,
            )

            # 更新 book_id 字段
            await session.run(
                """
                MATCH (n)
                WHERE n.book_id = $book_id AND n.book_ids IS NOT NULL AND size(n.book_ids) > 0
                SET n.book_id = n.book_ids[0]
                """,
                book_id=book_id,
            )

            # Step 3: 删除该书相关的跨书关系边
            result = await session.run(
                """
                MATCH (a)-[r]->(b)
                WHERE (
                    r.source_book = $book_id OR r.target_book = $book_id
                )
                AND (
                    type(r) = 'SAME_AS'
                    OR type(r) STARTS WITH 'CROSS_'
                )
                DELETE r
                RETURN count(r) AS deleted
                """,
                book_id=book_id,
            )
            record = await result.single()
            deleted_relations += record["deleted"] if record else 0

            # Step 4: 清理 MergeLog 节点
            # 情况 A: 该书实体是合并的"来源"
            await session.run(
                """
                MATCH (target)-[r:MERGED_FROM]->(log:MergeLog)
                WHERE log.source_book_id = $book_id
                DELETE r, log
                """,
                book_id=book_id,
            )

            # 情况 B: 该书实体是合并的"目标"
            await session.run(
                """
                MATCH (n)-[r:MERGED_FROM]->(log:MergeLog)
                WHERE $book_id IN coalesce(n.book_ids, [n.book_id])
                DELETE r, log
                """,
                book_id=book_id,
            )

            # Step 5: 删除该书的 Book 节点
            await session.run(
                """
                MATCH (b:Book {book_id: $book_id})
                DETACH DELETE b
                """,
                book_id=book_id,
            )

        return {"deleted_nodes": deleted_nodes, "deleted_relations": deleted_relations}

    def _cleanup_redis(self, book_id: str) -> bool:
        """清理 Redis 中的跨书数据。"""
        try:
            import redis
            r = get_sync_redis()

            # 删除所有相关的 key
            keys_to_delete = [
                f"d2g:cross_analysis:{book_id}",
                f"d2g:cross_decisions:{book_id}",
                f"d2g:cross_result:{book_id}",
                f"master_graph:{book_id}",
            ]

            deleted_count = 0
            for key in keys_to_delete:
                if r.delete(key):
                    deleted_count += 1

            logger.info("Redis 清理完成: %d 个 key 已删除", deleted_count)
            return True

        except Exception as e:
            logger.warning("Redis 清理失败: %s", e)
            return False

    def _cleanup_files(self, book_id: str) -> bool:
        """清理 JSON 文件。"""
        try:
            from src.config import settings

            # 删除跨书关系 JSON 文件
            json_path = Path(settings.data_dir) / book_id / "cross_book_relations.json"
            if json_path.exists():
                json_path.unlink()
                logger.info("已删除 JSON 文件: %s", json_path)

            # 删除跨书关系 MD 文件
            md_path = Path(settings.curation_md_dir) / book_id / "cross_book_relations.md"
            if md_path.exists():
                md_path.unlink()
                logger.info("已删除 MD 文件: %s", md_path)

            return True

        except Exception as e:
            logger.warning("文件清理失败: %s", e)
            return False

    async def verify_cleanup(self, book_id: str) -> dict:
        """验证清理是否彻底。

        Returns:
            验证结果
        """
        result = {
            "book_id": book_id,
            "neo4j_nodes_remaining": 0,
            "neo4j_relations_remaining": 0,
            "is_clean": True,
        }

        try:
            async with self._neo4j.session() as session:
                # 检查是否还有该书的节点
                node_result = await session.run(
                    """
                    MATCH (n)
                    WHERE $book_id IN coalesce(n.book_ids, [n.book_id])
                    RETURN count(n) AS cnt
                    """,
                    book_id=book_id,
                )
                record = await node_result.single()
                result["neo4j_nodes_remaining"] = record["cnt"] if record else 0

                # 检查是否还有跨书关系
                rel_result = await session.run(
                    """
                    MATCH ()-[r]->()
                    WHERE r.source_book = $book_id OR r.target_book = $book_id
                    RETURN count(r) AS cnt
                    """,
                    book_id=book_id,
                )
                record = await rel_result.single()
                result["neo4j_relations_remaining"] = record["cnt"] if record else 0

                # 判断是否清理干净
                if result["neo4j_nodes_remaining"] > 0 or result["neo4j_relations_remaining"] > 0:
                    result["is_clean"] = False

        except Exception as e:
            logger.warning("验证清理失败: %s", e)
            result["is_clean"] = False

        return result


# ── 便捷函数 ─────────────────────────────────────────────────


async def cleanup_cross_book_data(
    book_id: str,
    neo4j_driver,
) -> dict:
    """清理跨书数据的便捷入口。"""
    cleanup = CrossBookCleanup(neo4j_driver=neo4j_driver)
    return await cleanup.cleanup_book(book_id)


async def verify_cross_book_cleanup(
    book_id: str,
    neo4j_driver,
) -> dict:
    """验证跨书数据清理的便捷入口。"""
    cleanup = CrossBookCleanup(neo4j_driver=neo4j_driver)
    return await cleanup.verify_cleanup(book_id)
