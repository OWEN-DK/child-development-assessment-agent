"""测试用例草稿 Repository"""
from typing import Any, Dict, List, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from src.models.rag_eval.draft import TestCaseDraft
from src.repository.base import BaseRepository


class DraftRepository(BaseRepository[TestCaseDraft]):
    """测试用例草稿数据访问层"""

    def __init__(self, db_session_factory: async_sessionmaker):
        super().__init__(TestCaseDraft, db_session_factory)

    async def list_drafts(
        self,
        tenant_id: str,
        page: int = 1,
        page_size: int = 20,
        status: Optional[str] = None,
        search: Optional[str] = None,
    ) -> tuple[list[TestCaseDraft], int]:
        """分页查询草稿，支持状态和关键词筛选

        Returns:
            (草稿列表, 总数)
        """
        async with self.db_session_factory() as session:
            base_where = [TestCaseDraft.tenant_id == tenant_id]
            if status:
                base_where.append(TestCaseDraft.status == status)
            if search:
                escaped = search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
                base_where.append(TestCaseDraft.query.ilike(f"%{escaped}%"))

            count_stmt = select(func.count()).select_from(TestCaseDraft).where(*base_where)
            total = (await session.execute(count_stmt)).scalar() or 0

            stmt = (
                select(TestCaseDraft)
                .where(*base_where)
                .order_by(TestCaseDraft.created_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
            result = await session.execute(stmt)
            return list(result.scalars().all()), total

    async def get_by_id(self, id: str, tenant_id: Optional[str] = None) -> Optional[TestCaseDraft]:
        """根据 ID 查询单个草稿"""
        async with self.db_session_factory() as session:
            stmt = select(TestCaseDraft).where(TestCaseDraft.id == id)
            if tenant_id is not None:
                stmt = stmt.where(TestCaseDraft.tenant_id == tenant_id)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def create(self, obj_data: Dict[str, Any]) -> TestCaseDraft:
        """创建草稿"""
        return await super().create(obj_data)

    async def update(self, id: str, obj_data: Dict[str, Any], tenant_id: Optional[str] = None) -> TestCaseDraft:
        """更新草稿"""
        return await super().update(id, obj_data, tenant_id)

    async def delete(self, id: Any, tenant_id: Optional[str] = None) -> bool:
        """删除草稿"""
        return await super().delete(id, tenant_id)

    async def count_by_status(self, tenant_id: str) -> Dict[str, int]:
        """按状态统计草稿数量

        Returns:
            状态到数量的映射，如 {"pending": 5, "approved": 3}
        """
        async with self.db_session_factory() as session:
            stmt = (
                select(TestCaseDraft.status, func.count())
                .where(TestCaseDraft.tenant_id == tenant_id)
                .group_by(TestCaseDraft.status)
            )
            result = await session.execute(stmt)
            return {row[0]: row[1] for row in result.all()}
