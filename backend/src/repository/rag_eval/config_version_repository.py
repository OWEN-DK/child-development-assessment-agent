from typing import List

from sqlalchemy import desc
from sqlalchemy.ext.asyncio import async_sessionmaker

from src.core.database import async_session_factory as _default_session_factory
from src.models.rag_eval.config import EvalConfigVersion
from src.repository.base import BaseRepository


class ConfigVersionRepository(BaseRepository[EvalConfigVersion]):
    """评估配置版本 Repository

    注意：此表为 eval_config_versions，区别于系统 config_versions 表。
    """

    def __init__(self, db_session_factory: async_sessionmaker = _default_session_factory):
        super().__init__(EvalConfigVersion, db_session_factory)

    async def get_latest_version(self) -> EvalConfigVersion | None:
        """获取最新评估配置版本"""
        async with self.db_session_factory() as session:
            from sqlalchemy import select as _select

            result = await session.execute(
                _select(EvalConfigVersion)
                .order_by(desc(EvalConfigVersion.created_at))
                .limit(1)
            )
            return result.scalar_one_or_none()

    async def get_version_history(
        self, skip: int = 0, limit: int = 20
    ) -> List[EvalConfigVersion]:
        """获取评估配置版本历史"""
        return await self.get_all(
            skip=skip,
            limit=limit,
            order_by=desc(EvalConfigVersion.created_at),
        )

    async def get_by_creator(
        self, created_by: str, skip: int = 0, limit: int = 100
    ) -> List[EvalConfigVersion]:
        """根据创建者查询配置版本"""
        return await self.get_by_filter(
            created_by=created_by,
            skip=skip,
            limit=limit,
            order_by=desc(EvalConfigVersion.created_at),
        )
