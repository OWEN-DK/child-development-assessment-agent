from typing import List

from sqlalchemy import desc, select as _select
from sqlalchemy.ext.asyncio import async_sessionmaker

from src.core.database import async_session_factory as _default_session_factory
from src.models.rag_eval.test_run import TestRun
from src.repository.base import BaseRepository


class TestRunRepository(BaseRepository[TestRun]):
    def __init__(self, db_session_factory: async_sessionmaker = _default_session_factory):
        super().__init__(TestRun, db_session_factory)

    async def get_by_status(
        self, status: str, skip: int = 0, limit: int = 100
    ) -> List[TestRun]:
        """根据状态查询测试运行"""
        return await self.get_by_filter(
            status=status,
            skip=skip,
            limit=limit,
            order_by=desc(TestRun.created_at),
        )

    async def get_by_snapshot_id(
        self, snapshot_id: str, skip: int = 0, limit: int = 100
    ) -> List[TestRun]:
        """根据快照 ID 查询测试运行"""
        return await self.get_by_filter(
            snapshot_id=snapshot_id,
            skip=skip,
            limit=limit,
            order_by=desc(TestRun.created_at),
        )

    async def get_by_config_version(
        self, config_version_id: str, skip: int = 0, limit: int = 100
    ) -> List[TestRun]:
        """根据配置版本 ID 查询测试运行"""
        return await self.get_by_filter(
            config_version_id=config_version_id,
            skip=skip,
            limit=limit,
            order_by=desc(TestRun.created_at),
        )

    async def get_latest_runs(self, limit: int = 10) -> List[TestRun]:
        """获取最近测试运行列表"""
        async with self.db_session_factory() as session:
            result = await session.execute(
                _select(TestRun)
                .order_by(desc(TestRun.created_at))
                .limit(limit)
            )
            return list(result.scalars().all())
