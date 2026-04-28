from typing import List

from sqlalchemy import desc
from sqlalchemy.ext.asyncio import async_sessionmaker

from src.core.database import async_session_factory as _default_session_factory
from src.models.rag_eval.test_set import TestSet
from src.repository.base import BaseRepository


class TestSetRepository(BaseRepository[TestSet]):
    def __init__(self, db_session_factory: async_sessionmaker = _default_session_factory):
        super().__init__(TestSet, db_session_factory)

    async def get_by_source_type(
        self, source_type: str, skip: int = 0, limit: int = 100
    ) -> List[TestSet]:
        """根据来源类型查询测试集"""
        return await self.get_by_filter(
            source_type=source_type,
            skip=skip,
            limit=limit,
            order_by=desc(TestSet.created_at),
        )

    async def search_by_name(
        self, keyword: str, skip: int = 0, limit: int = 100
    ) -> List[TestSet]:
        """按名称模糊搜索测试集"""
        from sqlalchemy import select as _select

        async with self.db_session_factory() as session:
            result = await session.execute(
                _select(TestSet)
                .where(TestSet.name.contains(keyword))
                .order_by(desc(TestSet.created_at))
                .offset(skip)
                .limit(limit)
            )
            return list(result.scalars().all())
