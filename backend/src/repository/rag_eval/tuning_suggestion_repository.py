from typing import List

from sqlalchemy import desc
from sqlalchemy.ext.asyncio import async_sessionmaker

from src.core.database import async_session_factory as _default_session_factory
from src.models.rag_eval.tuning import TuningSuggestion
from src.repository.base import BaseRepository


class TuningSuggestionRepository(BaseRepository[TuningSuggestion]):
    def __init__(self, db_session_factory: async_sessionmaker = _default_session_factory):
        super().__init__(TuningSuggestion, db_session_factory)

    async def get_by_run_id(
        self, run_id: str, skip: int = 0, limit: int = 100
    ) -> List[TuningSuggestion]:
        """查询指定运行的所有调优建议"""
        return await self.get_by_filter(
            run_id=run_id,
            skip=skip,
            limit=limit,
            order_by=desc(TuningSuggestion.priority),
        )

    async def get_by_report_id(
        self, report_id: str, skip: int = 0, limit: int = 100
    ) -> List[TuningSuggestion]:
        """查询指定报告的所有调优建议"""
        return await self.get_by_filter(
            report_id=report_id,
            skip=skip,
            limit=limit,
            order_by=desc(TuningSuggestion.priority),
        )

    async def get_by_status(
        self, status: str, skip: int = 0, limit: int = 100
    ) -> List[TuningSuggestion]:
        """根据状态查询调优建议"""
        return await self.get_by_filter(
            status=status,
            skip=skip,
            limit=limit,
            order_by=desc(TuningSuggestion.priority),
        )

    async def get_by_category(
        self, category: str, skip: int = 0, limit: int = 100
    ) -> List[TuningSuggestion]:
        """根据类别查询调优建议"""
        return await self.get_by_filter(
            category=category,
            skip=skip,
            limit=limit,
            order_by=desc(TuningSuggestion.priority),
        )

    async def get_top_by_priority(
        self, run_id: str, limit: int = 10
    ) -> List[TuningSuggestion]:
        """获取指定运行的 Top-N 优先级建议"""
        async with self.db_session_factory() as session:
            from sqlalchemy import select as _select

            result = await session.execute(
                _select(TuningSuggestion)
                .where(TuningSuggestion.run_id == run_id)
                .order_by(desc(TuningSuggestion.priority))
                .limit(limit)
            )
            return list(result.scalars().all())
