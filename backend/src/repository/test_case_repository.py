from typing import Optional, List
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import async_sessionmaker
from src.repository.base import BaseRepository
from src.models.test_case import (
    TestCase,
    TestCaseDraft,
    TestSet,
    TestSetCase,
    TestRun,
    TestRunResult,
)


class TestCaseRepository(BaseRepository[TestCase]):
    def __init__(self, db_session_factory: async_sessionmaker):
        super().__init__(TestCase, db_session_factory)

    async def get_by_domain(
        self, domain: str, skip: int = 0, limit: int = 50
    ) -> List[TestCase]:
        """根据领域查询测试用例"""
        return await self.get_by_filter(skip=skip, limit=limit, domain=domain)

    async def get_by_age_range(self, age_min: float, age_max: float) -> List[TestCase]:
        """根据年龄范围查询测试用例"""
        async with self.db_session_factory() as session:
            result = await session.execute(
                select(TestCase).where(TestCase.age >= age_min, TestCase.age <= age_max)
            )
            return list(result.scalars().all())


class TestCaseDraftRepository(BaseRepository[TestCaseDraft]):
    def __init__(self, db_session_factory: async_sessionmaker):
        super().__init__(TestCaseDraft, db_session_factory)

    async def get_by_status(
        self, status: str, skip: int = 0, limit: int = 50
    ) -> List[TestCaseDraft]:
        """根据状态查询草稿"""
        return await self.get_by_filter(skip=skip, limit=limit, status=status)

    async def get_by_source_document(
        self, source_document_id: str
    ) -> List[TestCaseDraft]:
        """根据源文档ID查询草稿"""
        return await self.get_by_filter(source_document_id=source_document_id)


class TestSetRepository(BaseRepository[TestSet]):
    def __init__(self, db_session_factory: async_sessionmaker):
        super().__init__(TestSet, db_session_factory)


class TestSetCaseRepository(BaseRepository[TestSetCase]):
    def __init__(self, db_session_factory: async_sessionmaker):
        super().__init__(TestSetCase, db_session_factory)

    async def get_cases_by_test_set(self, test_set_id: str) -> List[TestSetCase]:
        """获取测试集的所有用例关联"""
        return await self.get_by_filter(test_set_id=test_set_id)

    async def get_test_sets_by_case(self, test_case_id: str) -> List[TestSetCase]:
        """反向查询：获取包含指定用例的所有测试集"""
        return await self.get_by_filter(test_case_id=test_case_id)

    async def add_case_to_set(self, test_set_id: str, test_case_id: str) -> TestSetCase:
        """添加用例到测试集"""
        return await self.create(
            {"test_set_id": test_set_id, "test_case_id": test_case_id}
        )

    async def remove_case_from_set(self, test_set_id: str, test_case_id: str) -> bool:
        """从测试集移除用例"""
        from sqlalchemy import delete

        async with self.db_session_factory() as session:
            result = await session.execute(
                delete(TestSetCase).where(
                    TestSetCase.test_set_id == test_set_id,
                    TestSetCase.test_case_id == test_case_id,
                )
            )
            await session.commit()
            return result.rowcount > 0

    async def get_test_cases_by_set_id(self, test_set_id: str) -> List["TestCase"]:
        """通过JOIN查询获取测试集的所有测试用例

        注意: TestCase和TestSet通过TestSetCase中间表关联，不能直接过滤
        """
        async with self.db_session_factory() as session:
            result = await session.execute(
                select(TestCase)
                .join(TestSetCase, TestCase.id == TestSetCase.test_case_id)
                .where(TestSetCase.test_set_id == test_set_id)
            )
            return list(result.scalars().all())


class TestRunRepository(BaseRepository[TestRun]):
    def __init__(self, db_session_factory: async_sessionmaker):
        super().__init__(TestRun, db_session_factory)

    async def get_latest_runs(self, limit: int = 10) -> List[TestRun]:
        """获取最近的测试运行"""
        return await self.get_all(
            skip=0, limit=limit, order_by=desc(TestRun.created_at)
        )


class TestRunResultRepository(BaseRepository[TestRunResult]):
    def __init__(self, db_session_factory: async_sessionmaker):
        super().__init__(TestRunResult, db_session_factory)

    async def get_by_run_id(self, run_id: str) -> List[TestRunResult]:
        """根据运行ID查询所有结果"""
        return await self.get_by_filter(run_id=run_id)
