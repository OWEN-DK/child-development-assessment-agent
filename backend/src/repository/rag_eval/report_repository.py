from typing import List

from sqlalchemy import desc
from sqlalchemy.ext.asyncio import async_sessionmaker

from src.core.database import async_session_factory as _default_session_factory
from src.models.rag_eval.report import EvalReport
from src.repository.base import BaseRepository


class ReportRepository(BaseRepository[EvalReport]):
    def __init__(self, db_session_factory: async_sessionmaker = _default_session_factory):
        super().__init__(EvalReport, db_session_factory)

    async def get_by_run_id(
        self, run_id: str
    ) -> List[EvalReport]:
        """查询指定运行的所有报告"""
        return await self.get_by_filter(
            run_id=run_id,
            order_by=desc(EvalReport.created_at),
        )

    async def get_by_test_set_id(
        self, test_set_id: str, skip: int = 0, limit: int = 100
    ) -> List[EvalReport]:
        """查询指定测试集的所有报告"""
        return await self.get_by_filter(
            test_set_id=test_set_id,
            skip=skip,
            limit=limit,
            order_by=desc(EvalReport.created_at),
        )

    async def get_by_status(
        self, status: str, skip: int = 0, limit: int = 100
    ) -> List[EvalReport]:
        """根据状态查询报告"""
        return await self.get_by_filter(
            status=status,
            skip=skip,
            limit=limit,
            order_by=desc(EvalReport.created_at),
        )

    async def get_latest_by_run(self, run_id: str) -> EvalReport | None:
        """获取指定运行的最新报告"""
        async with self.db_session_factory() as session:
            from sqlalchemy import select as _select

            result = await session.execute(
                _select(EvalReport)
                .where(EvalReport.run_id == run_id)
                .order_by(desc(EvalReport.created_at))
                .limit(1)
            )
            return result.scalar_one_or_none()
