from typing import List

from sqlalchemy import select as _select
from sqlalchemy.ext.asyncio import async_sessionmaker

from src.core.database import async_session_factory as _default_session_factory
from src.models.rag_eval.test_set_case import TestSetCase
from src.repository.base import BaseRepository


class TestSetCaseRepository(BaseRepository[TestSetCase]):
    def __init__(self, db_session_factory: async_sessionmaker = _default_session_factory):
        super().__init__(TestSetCase, db_session_factory)

    async def get_by_test_set(
        self, test_set_id: str
    ) -> List[TestSetCase]:
        """查询测试集中的所有用例关联"""
        return await self.get_by_filter(
            test_set_id=test_set_id,
            order_by=TestSetCase.added_at,
        )

    async def get_by_test_case(
        self, test_case_id: str
    ) -> List[TestSetCase]:
        """查询用例关联的所有测试集"""
        return await self.get_by_filter(test_case_id=test_case_id)

    async def remove_by_set_and_case(
        self, test_set_id: str, test_case_id: str
    ) -> bool:
        """从测试集中移除指定用例"""
        from sqlalchemy import delete

        async with self.db_session_factory() as session:
            result = await session.execute(
                delete(TestSetCase)
                .where(TestSetCase.test_set_id == test_set_id)
                .where(TestSetCase.test_case_id == test_case_id)
            )
            await session.commit()
            return result.rowcount > 0

    async def count_by_test_set(self, test_set_id: str) -> int:
        """统计测试集中的用例数量"""
        return await self.count_by_filter(test_set_id=test_set_id)
