"""测试集 Repository"""
from typing import Any, Dict, List, Optional

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from src.models.rag_eval.test_case import TestSet, TestSetCase
from src.repository.base import BaseRepository


class TestSetRepository(BaseRepository[TestSet]):
    """测试集数据访问层"""

    def __init__(self, db_session_factory: async_sessionmaker):
        super().__init__(TestSet, db_session_factory)

    async def list_sets(
        self,
        tenant_id: str,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[TestSet], int]:
        """分页查询测试集

        Returns:
            (测试集列表, 总数)
        """
        async with self.db_session_factory() as session:
            where = TestSet.tenant_id == tenant_id

            count_stmt = select(func.count()).select_from(TestSet).where(where)
            total = (await session.execute(count_stmt)).scalar() or 0

            stmt = (
                select(TestSet)
                .where(where)
                .order_by(TestSet.created_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
            result = await session.execute(stmt)
            return list(result.scalars().all()), total

    async def get_by_id(self, id: str, tenant_id: Optional[str] = None) -> Optional[TestSet]:
        """根据 ID 查询单个测试集"""
        async with self.db_session_factory() as session:
            stmt = select(TestSet).where(TestSet.id == id)
            if tenant_id is not None:
                stmt = stmt.where(TestSet.tenant_id == tenant_id)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def create(self, obj_data: Dict[str, Any]) -> TestSet:
        """创建测试集"""
        return await super().create(obj_data)

    async def update(self, id: str, obj_data: Dict[str, Any], tenant_id: Optional[str] = None) -> TestSet:
        """更新测试集"""
        return await super().update(id, obj_data, tenant_id)

    async def delete(self, id: Any, tenant_id: Optional[str] = None) -> bool:
        """删除测试集"""
        return await super().delete(id, tenant_id)

    async def add_cases(self, set_id: str, case_ids: List[str]) -> None:
        """向测试集中添加用例关联"""
        async with self.db_session_factory() as session:
            for index, case_id in enumerate(case_ids):
                session.add(TestSetCase(set_id=set_id, case_id=case_id, sort_order=index))
            await session.commit()

    async def remove_cases(self, set_id: str, case_ids: List[str]) -> int:
        """从测试集中移除用例关联

        Returns:
            实际删除的行数
        """
        async with self.db_session_factory() as session:
            stmt = delete(TestSetCase).where(
                TestSetCase.set_id == set_id,
                TestSetCase.case_id.in_(case_ids),
            )
            result = await session.execute(stmt)
            await session.commit()
            return result.rowcount
