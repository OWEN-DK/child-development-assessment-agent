from typing import List, Optional

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from src.core.database import async_session_factory as _default_session_factory
from src.models.rag_eval.test_case import TestCase
from src.repository.base import BaseRepository


class TestCaseRepository(BaseRepository[TestCase]):
    def __init__(self, db_session_factory: async_sessionmaker = _default_session_factory):
        super().__init__(TestCase, db_session_factory)

    async def get_by_domain(
        self, domain: str, skip: int = 0, limit: int = 100
    ) -> List[TestCase]:
        """根据领域查询测试用例"""
        return await self.get_by_filter(
            domain=domain,
            skip=skip,
            limit=limit,
            order_by=desc(TestCase.created_at),
        )

    async def get_by_age_stage(
        self, age_stage_label: str, skip: int = 0, limit: int = 100
    ) -> List[TestCase]:
        """根据年龄段查询测试用例"""
        return await self.get_by_filter(
            age_stage_label=age_stage_label,
            skip=skip,
            limit=limit,
            order_by=desc(TestCase.created_at),
        )

    async def get_by_source(
        self, source: str, skip: int = 0, limit: int = 100
    ) -> List[TestCase]:
        """根据来源查询测试用例"""
        return await self.get_by_filter(
            source=source,
            skip=skip,
            limit=limit,
            order_by=desc(TestCase.created_at),
        )

    async def get_by_source_draft(
        self, source_draft_id: str
    ) -> Optional[TestCase]:
        """根据来源草稿 ID 查询测试用例"""
        return await self.get_one_by_filter(source_draft_id=source_draft_id)

    async def search_by_query(
        self, keyword: str, skip: int = 0, limit: int = 100
    ) -> List[TestCase]:
        """按问题文本模糊搜索"""
        async with self.db_session_factory() as session:
            result = await session.execute(
                select(TestCase)
                .where(TestCase.query.contains(keyword))
                .order_by(desc(TestCase.created_at))
                .offset(skip)
                .limit(limit)
            )
            return list(result.scalars().all())
