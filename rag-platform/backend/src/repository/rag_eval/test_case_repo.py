"""测试用例 Repository"""
from typing import Any, Dict, List, Optional

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from src.models.rag_eval.test_case import TestCase
from src.repository.base import BaseRepository


class TestCaseRepository(BaseRepository[TestCase]):
    """测试用例数据访问层"""

    def __init__(self, db_session_factory: async_sessionmaker):
        super().__init__(TestCase, db_session_factory)

    async def list_cases(
        self,
        tenant_id: str,
        page: int = 1,
        page_size: int = 20,
        source: Optional[str] = None,
        difficulty: Optional[str] = None,
        search: Optional[str] = None,
    ) -> tuple[list[TestCase], int]:
        """分页查询测试用例，支持来源、难度和关键词筛选

        Returns:
            (用例列表, 总数)
        """
        async with self.db_session_factory() as session:
            base_where = [TestCase.tenant_id == tenant_id]
            if source:
                base_where.append(TestCase.source == source)
            if difficulty:
                base_where.append(TestCase.difficulty_level == difficulty)
            if search:
                escaped = search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
                base_where.append(TestCase.query.ilike(f"%{escaped}%"))

            # 查总数
            count_stmt = select(func.count()).select_from(TestCase).where(*base_where)
            total = (await session.execute(count_stmt)).scalar() or 0

            # 查数据
            stmt = (
                select(TestCase)
                .where(*base_where)
                .order_by(TestCase.created_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
            result = await session.execute(stmt)
            return list(result.scalars().all()), total

    async def get_by_id(self, id: str, tenant_id: Optional[str] = None) -> Optional[TestCase]:
        """根据 ID 查询单个用例"""
        async with self.db_session_factory() as session:
            stmt = select(TestCase).where(TestCase.id == id)
            if tenant_id is not None:
                stmt = stmt.where(TestCase.tenant_id == tenant_id)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def create(self, obj_data: Dict[str, Any]) -> TestCase:
        """创建测试用例"""
        return await super().create(obj_data)

    async def update(self, id: str, obj_data: Dict[str, Any], tenant_id: Optional[str] = None) -> TestCase:
        """更新测试用例"""
        return await super().update(id, obj_data, tenant_id)

    async def delete(self, id: Any, tenant_id: Optional[str] = None) -> bool:
        """删除测试用例"""
        return await super().delete(id, tenant_id)

    async def batch_delete(self, ids: List[str], tenant_id: Optional[str] = None) -> int:
        """批量删除测试用例

        Returns:
            实际删除的行数
        """
        async with self.db_session_factory() as session:
            stmt = delete(TestCase).where(TestCase.id.in_(ids))
            if tenant_id is not None:
                stmt = stmt.where(TestCase.tenant_id == tenant_id)
            result = await session.execute(stmt)
            await session.commit()
            return result.rowcount

    async def count_by_tenant(self, tenant_id: str) -> int:
        """统计租户下的测试用例数量"""
        return await super().count(tenant_id)
