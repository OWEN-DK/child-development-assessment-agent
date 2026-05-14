"""知识库 Repository"""
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from src.models.knowledge_base import KnowledgeBase
from src.repository.base import BaseRepository


class KnowledgeBaseRepository(BaseRepository[KnowledgeBase]):
    """知识库数据访问层"""

    def __init__(self, db_session_factory: async_sessionmaker):
        super().__init__(KnowledgeBase, db_session_factory)

    async def count_by_tenant(self, tenant_id: str) -> int:
        """统计租户下的知识库数量"""
        async with self.db_session_factory() as session:
            stmt = select(func.count()).select_from(KnowledgeBase).where(
                KnowledgeBase.tenant_id == tenant_id
            )
            result = await session.execute(stmt)
            return result.scalar() or 0

    async def search(
        self,
        tenant_id: str,
        keyword: Optional[str] = None,
        vector_backend: Optional[str] = None,
        status: Optional[str] = None,
        visibility: Optional[str] = None,
        skip: int = 0,
        limit: int = 20,
    ) -> list[KnowledgeBase]:
        """多条件筛选知识库"""
        async with self.db_session_factory() as session:
            stmt = select(KnowledgeBase).where(KnowledgeBase.tenant_id == tenant_id)

            if keyword:
                stmt = stmt.where(KnowledgeBase.name.ilike(f"%{keyword}%"))
            if vector_backend:
                stmt = stmt.where(KnowledgeBase.vector_backend == vector_backend)
            if status:
                stmt = stmt.where(KnowledgeBase.status == status)
            if visibility:
                stmt = stmt.where(KnowledgeBase.visibility == visibility)

            stmt = stmt.order_by(KnowledgeBase.created_at.desc())
            stmt = stmt.offset(skip).limit(limit)

            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def update_status(self, kb_id: str, tenant_id: str, status: str) -> None:
        """更新知识库状态"""
        async with self.db_session_factory() as session:
            stmt = select(KnowledgeBase).where(
                KnowledgeBase.id == kb_id,
                KnowledgeBase.tenant_id == tenant_id,
            )
            result = await session.execute(stmt)
            kb = result.scalar_one_or_none()
            if kb:
                kb.status = status
                await session.commit()

    async def increment_counts(
        self, kb_id: str, tenant_id: str, doc_delta: int = 0, chunk_delta: int = 0
    ) -> None:
        """增量更新文档数和分块数"""
        async with self.db_session_factory() as session:
            stmt = select(KnowledgeBase).where(
                KnowledgeBase.id == kb_id,
                KnowledgeBase.tenant_id == tenant_id,
            )
            result = await session.execute(stmt)
            kb = result.scalar_one_or_none()
            if kb:
                kb.document_count = max(0, kb.document_count + doc_delta)
                kb.chunk_count = max(0, kb.chunk_count + chunk_delta)
                await session.commit()
