"""知识图谱数据访问层 — LazyGraphRAG 存储操作

提供实体/关系/社区树的 CRUD 与批量写入，每个方法独立管理 session 生命周期。
"""

import logging
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from src.models.graph import GraphCommunityNode, GraphEntity, GraphRelation
from src.repository.base import BaseRepository

logger = logging.getLogger(__name__)


class GraphEntityRepository(BaseRepository[GraphEntity]):
    """知识图谱实体仓库"""

    def __init__(self, db_session_factory: async_sessionmaker):
        super().__init__(GraphEntity, db_session_factory)

    async def batch_upsert(self, entities: list[GraphEntity]) -> int:
        """批量插入实体（同名实体覆盖更新）"""
        async with self.db_session_factory() as session:
            for entity in entities:
                # 查找同名同书实体
                existing = await session.execute(
                    select(GraphEntity).where(
                        GraphEntity.name == entity.name,
                        GraphEntity.book_id == entity.book_id,
                    )
                )
                old = existing.scalar_one_or_none()
                if old:
                    # 合并 chunk_ids 和 aliases
                    old_chunk_ids = old.chunk_ids or []
                    new_chunk_ids = entity.chunk_ids or []
                    merged_chunks = list(dict.fromkeys(
                        str(c) for c in old_chunk_ids + new_chunk_ids
                    ))
                    old.chunk_ids = merged_chunks
                    if entity.aliases:
                        old_aliases = old.aliases or []
                        merged_aliases = list(dict.fromkeys(old_aliases + entity.aliases))
                        old.aliases = merged_aliases
                    if entity.description and not old.description:
                        old.description = entity.description
                else:
                    session.add(entity)
            await session.commit()
        return len(entities)

    async def find_by_book(self, book_id: str) -> list[GraphEntity]:
        async with self.db_session_factory() as session:
            result = await session.execute(
                select(GraphEntity).where(GraphEntity.book_id == book_id)
            )
            return list(result.scalars().all())

    async def find_all(self) -> list[GraphEntity]:
        """加载所有实体（全局图重建用）"""
        async with self.db_session_factory() as session:
            result = await session.execute(select(GraphEntity))
            return list(result.scalars().all())

    async def get_by_id(self, entity_id: int) -> Optional[GraphEntity]:
        async with self.db_session_factory() as session:
            result = await session.execute(
                select(GraphEntity).where(GraphEntity.id == entity_id)
            )
            return result.scalar_one_or_none()



    async def delete_by_book(self, book_id: str) -> int:
        """删除指定书籍的所有实体（级联清理用）"""
        async with self.db_session_factory() as session:
            result = await session.execute(
                select(GraphEntity).where(GraphEntity.book_id == book_id)
            )
            entities = list(result.scalars().all())
            for entity in entities:
                await session.delete(entity)
            await session.commit()
        return len(entities)


class GraphRelationRepository(BaseRepository[GraphRelation]):
    """知识图谱关系仓库"""

    def __init__(self, db_session_factory: async_sessionmaker):
        super().__init__(GraphRelation, db_session_factory)

    async def batch_insert(self, relations: list[GraphRelation]) -> int:
        async with self.db_session_factory() as session:
            session.add_all(relations)
            await session.commit()
        return len(relations)

    async def find_by_book(self, book_id: str) -> list[GraphRelation]:
        async with self.db_session_factory() as session:
            result = await session.execute(
                select(GraphRelation).where(GraphRelation.book_id == book_id)
            )
            return list(result.scalars().all())

    async def find_all(self) -> list[GraphRelation]:
        """加载所有关系（全局图重建用）"""
        async with self.db_session_factory() as session:
            result = await session.execute(select(GraphRelation))
            return list(result.scalars().all())

    async def find_by_entity_ids(self, entity_ids: list[int]) -> list[GraphRelation]:
        async with self.db_session_factory() as session:
            result = await session.execute(
                select(GraphRelation).where(
                    GraphRelation.source_entity_id.in_(entity_ids)
                    | GraphRelation.target_entity_id.in_(entity_ids)
                )
            )
            return list(result.scalars().all())

    async def delete_by_book(self, book_id: str) -> int:
        """删除指定书籍的所有关系（级联清理用）"""
        async with self.db_session_factory() as session:
            result = await session.execute(
                select(GraphRelation).where(GraphRelation.book_id == book_id)
            )
            relations = list(result.scalars().all())
            for rel in relations:
                await session.delete(rel)
            await session.commit()
        return len(relations)


class GraphCommunityRepository(BaseRepository[GraphCommunityNode]):
    """层级社区树仓库"""

    def __init__(self, db_session_factory: async_sessionmaker):
        super().__init__(GraphCommunityNode, db_session_factory)

    async def batch_insert(self, nodes: list[GraphCommunityNode]) -> int:
        async with self.db_session_factory() as session:
            session.add_all(nodes)
            await session.commit()
        return len(nodes)

    async def get_node(self, node_id: str) -> Optional[GraphCommunityNode]:
        async with self.db_session_factory() as session:
            result = await session.execute(
                select(GraphCommunityNode).where(GraphCommunityNode.node_id == node_id)
            )
            return result.scalar_one_or_none()

    async def get_children(self, parent_id: str) -> list[GraphCommunityNode]:
        async with self.db_session_factory() as session:
            result = await session.execute(
                select(GraphCommunityNode).where(
                    GraphCommunityNode.parent_id == parent_id
                )
            )
            return list(result.scalars().all())

    async def get_children_batch(self, parent_ids: list[str]) -> dict[str, list[GraphCommunityNode]]:
        """批量查询多个父节点的子节点，单次 DB 查询。

        Returns:
            {parent_id: [children]} 映射，无子节点的 parent 不在 key 中
        """
        if not parent_ids:
            return {}
        async with self.db_session_factory() as session:
            result = await session.execute(
                select(GraphCommunityNode).where(
                    GraphCommunityNode.parent_id.in_(parent_ids)
                )
            )
            rows = list(result.scalars().all())
        # 按 parent_id 分组
        children_map: dict[str, list[GraphCommunityNode]] = {}
        for row in rows:
            children_map.setdefault(row.parent_id, []).append(row)
        return children_map

    async def get_roots(self, scope: str = "book", book_id: str | None = None) -> list[GraphCommunityNode]:
        """获取根节点（parent_id 为 NULL）"""
        async with self.db_session_factory() as session:
            stmt = select(GraphCommunityNode).where(
                GraphCommunityNode.parent_id.is_(None),
                GraphCommunityNode.scope == scope,
            )
            if book_id is not None:
                stmt = stmt.where(GraphCommunityNode.book_id == book_id)
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def get_leaves_by_entity_names(
        self, entity_names: list[str], book_id: str | None = None
    ) -> list[GraphCommunityNode]:
        """根据实体名查找所属叶子社区（用于从检索结果反查社区）"""
        async with self.db_session_factory() as session:
            stmt = select(GraphCommunityNode).where(
                GraphCommunityNode.is_leaf.is_(True)
            )
            if book_id is not None:
                stmt = stmt.where(GraphCommunityNode.book_id == book_id)
            result = await session.execute(stmt)
            all_leaves = list(result.scalars().all())

        matching = []
        for leaf in all_leaves:
            names = leaf.entity_names or []
            if any(name in entity_names for name in names):
                matching.append(leaf)
        return matching

    async def delete_by_book(self, book_id: str) -> int:
        """删除指定书籍的所有社区节点（重建前清理）"""
        async with self.db_session_factory() as session:
            result = await session.execute(
                select(GraphCommunityNode).where(GraphCommunityNode.book_id == book_id)
            )
            nodes = list(result.scalars().all())
            for node in nodes:
                await session.delete(node)
            await session.commit()
            return len(nodes)

    async def delete_by_scope(self, scope: str) -> int:
        """删除指定作用域的所有社区节点（全局图重建前清理）"""
        from src.models.graph import CommunityScope
        async with self.db_session_factory() as session:
            result = await session.execute(
                select(GraphCommunityNode).where(
                    GraphCommunityNode.scope == scope
                )
            )
            nodes = list(result.scalars().all())
            for node in nodes:
                await session.delete(node)
            await session.commit()
            return len(nodes)
