"""分块 Repository"""
from typing import Optional

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from src.models.kb_chunk import KbChunk
from src.repository.base import BaseRepository


class ChunkRepository(BaseRepository[KbChunk]):
    """分块数据访问层"""

    def __init__(self, db_session_factory: async_sessionmaker):
        super().__init__(KbChunk, db_session_factory)

    async def batch_insert(self, chunks: list[dict]) -> int:
        """批量插入分块"""
        async with self.db_session_factory() as session:
            for chunk_data in chunks:
                session.add(KbChunk(**chunk_data))
            await session.commit()
            return len(chunks)

    async def get_by_doc_id(
        self, doc_id: str, tenant_id: str, limit: int = 10, offset: int = 0
    ) -> list[KbChunk]:
        """获取文档的分块（预览用）"""
        async with self.db_session_factory() as session:
            stmt = select(KbChunk).where(
                KbChunk.doc_id == doc_id,
                KbChunk.tenant_id == tenant_id,
            ).order_by(KbChunk.chunk_index).offset(offset).limit(limit)
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def delete_by_doc_id(self, doc_id: str, tenant_id: str) -> int:
        """删除文档的所有分块"""
        async with self.db_session_factory() as session:
            stmt = delete(KbChunk).where(
                KbChunk.doc_id == doc_id,
                KbChunk.tenant_id == tenant_id,
            )
            result = await session.execute(stmt)
            await session.commit()
            return result.rowcount

    async def count_by_doc(self, doc_id: str, tenant_id: str) -> int:
        """统计文档的分块数"""
        async with self.db_session_factory() as session:
            stmt = select(func.count()).select_from(KbChunk).where(
                KbChunk.doc_id == doc_id,
                KbChunk.tenant_id == tenant_id,
            )
            result = await session.execute(stmt)
            return result.scalar() or 0

    async def count_by_kb(self, kb_id: str, tenant_id: str) -> int:
        """统计知识库的分块数"""
        async with self.db_session_factory() as session:
            stmt = select(func.count()).select_from(KbChunk).where(
                KbChunk.kb_id == kb_id,
                KbChunk.tenant_id == tenant_id,
            )
            result = await session.execute(stmt)
            return result.scalar() or 0

    async def delete_by_kb(self, kb_id: str, tenant_id: str) -> int:
        """删除知识库的所有分块"""
        async with self.db_session_factory() as session:
            stmt = delete(KbChunk).where(
                KbChunk.kb_id == kb_id,
                KbChunk.tenant_id == tenant_id,
            )
            result = await session.execute(stmt)
            await session.commit()
            return result.rowcount

    async def get_chunk_ids_by_doc(self, doc_id: str, tenant_id: str) -> list[str]:
        """获取文档的所有分块 ID"""
        async with self.db_session_factory() as session:
            stmt = select(KbChunk.id).where(
                KbChunk.doc_id == doc_id,
                KbChunk.tenant_id == tenant_id,
            )
            result = await session.execute(stmt)
            return [row[0] for row in result.all()]
