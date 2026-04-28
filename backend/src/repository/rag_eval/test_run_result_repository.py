from typing import List

from sqlalchemy.ext.asyncio import async_sessionmaker

from src.core.database import async_session_factory as _default_session_factory
from src.models.rag_eval.test_run_result import TestRunResult
from src.repository.base import BaseRepository


class TestRunResultRepository(BaseRepository[TestRunResult]):
    def __init__(self, db_session_factory: async_sessionmaker = _default_session_factory):
        super().__init__(TestRunResult, db_session_factory)

    async def get_by_run_id(
        self, run_id: str, skip: int = 0, limit: int = 1000
    ) -> List[TestRunResult]:
        """查询指定运行的所有测试结果"""
        return await self.get_by_filter(
            run_id=run_id,
            skip=skip,
            limit=limit,
        )

    async def get_by_test_case_id(
        self, test_case_id: str, skip: int = 0, limit: int = 100
    ) -> List[TestRunResult]:
        """查询指定用例的全部历史运行结果"""
        return await self.get_by_filter(
            test_case_id=test_case_id,
            skip=skip,
            limit=limit,
        )

    async def get_passed_results_by_run(
        self, run_id: str, skip: int = 0, limit: int = 1000
    ) -> List[TestRunResult]:
        """查询指定运行中通过的测试结果"""
        async with self.db_session_factory() as session:
            from sqlalchemy import select as _select

            result = await session.execute(
                _select(TestRunResult)
                .where(TestRunResult.run_id == run_id)
                .where(TestRunResult.passed == True)
                .offset(skip)
                .limit(limit)
            )
            return list(result.scalars().all())

    async def get_failed_results_by_run(
        self, run_id: str, skip: int = 0, limit: int = 1000
    ) -> List[TestRunResult]:
        """查询指定运行中失败的测试结果"""
        async with self.db_session_factory() as session:
            from sqlalchemy import select as _select

            result = await session.execute(
                _select(TestRunResult)
                .where(TestRunResult.run_id == run_id)
                .where(TestRunResult.passed == False)
                .offset(skip)
                .limit(limit)
            )
            return list(result.scalars().all())

    async def count_by_run_id(self, run_id: str) -> int:
        """统计指定运行的结果数量"""
        return await self.count_by_filter(run_id=run_id)
