"""知识库快照 Repository"""
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from src.models.rag_eval.snapshot import KnowledgeSnapshot
from src.repository.base import BaseRepository


class SnapshotRepository(BaseRepository[KnowledgeSnapshot]):
    """知识库快照数据访问层"""

    def __init__(self, db_session_factory: async_sessionmaker):
        super().__init__(KnowledgeSnapshot, db_session_factory)

    async def list_snapshots(
        self,
        tenant_id: str,
        kb_id: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[KnowledgeSnapshot], int]:
        """分页查询知识库快照，支持按知识库筛选

        Returns:
            (快照列表, 总数)
        """
        async with self.db_session_factory() as session:
            base_where = [KnowledgeSnapshot.tenant_id == tenant_id]
            if kb_id:
                base_where.append(KnowledgeSnapshot.kb_id == kb_id)

            count_stmt = select(func.count()).select_from(KnowledgeSnapshot).where(*base_where)
            total = (await session.execute(count_stmt)).scalar() or 0

            stmt = (
                select(KnowledgeSnapshot)
                .where(*base_where)
                .order_by(KnowledgeSnapshot.created_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
            result = await session.execute(stmt)
            return list(result.scalars().all()), total

    async def get_by_id(self, id: str, tenant_id: Optional[str] = None) -> Optional[KnowledgeSnapshot]:
        """根据 ID 查询单个快照"""
        async with self.db_session_factory() as session:
            stmt = select(KnowledgeSnapshot).where(KnowledgeSnapshot.id == id)
            if tenant_id is not None:
                stmt = stmt.where(KnowledgeSnapshot.tenant_id == tenant_id)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def create(self, obj_data: Dict[str, Any]) -> KnowledgeSnapshot:
        """创建快照"""
        return await super().create(obj_data)

    async def update_status(self, id: str, status: str, tenant_id: Optional[str] = None) -> KnowledgeSnapshot:
        """更新快照状态

        Args:
            id: 快照 ID
            status: 目标状态（active/invalid/expired）
            tenant_id: 租户 ID
        """
        async with self.db_session_factory() as session:
            stmt = select(KnowledgeSnapshot).where(KnowledgeSnapshot.id == id)
            if tenant_id is not None:
                stmt = stmt.where(KnowledgeSnapshot.tenant_id == tenant_id)
            result = await session.execute(stmt)
            snapshot = result.scalar_one_or_none()
            if snapshot is None:
                raise ValueError(f"KnowledgeSnapshot with id={id} not found")
            snapshot.status = status
            await session.commit()
            await session.refresh(snapshot)
            return snapshot

    async def cleanup_expired(self) -> int:
        """清理已过期的快照（状态置为 expired）

        Returns:
            标记为过期的快照数量
        """
        async with self.db_session_factory() as session:
            now = datetime.utcnow()
            stmt = select(KnowledgeSnapshot).where(
                KnowledgeSnapshot.status == "active",
                KnowledgeSnapshot.expires_at.isnot(None),
                KnowledgeSnapshot.expires_at < now,
            )
            result = await session.execute(stmt)
            expired = list(result.scalars().all())
            for snapshot in expired:
                snapshot.status = "expired"
            await session.commit()
            return len(expired)
