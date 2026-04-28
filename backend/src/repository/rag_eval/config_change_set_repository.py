from typing import List

from sqlalchemy import desc
from sqlalchemy.ext.asyncio import async_sessionmaker

from src.core.database import async_session_factory as _default_session_factory
from src.models.rag_eval.config import EvalConfigChangeSet
from src.repository.base import BaseRepository


class ConfigChangeSetRepository(BaseRepository[EvalConfigChangeSet]):
    """评估配置变更集 Repository"""

    def __init__(self, db_session_factory: async_sessionmaker = _default_session_factory):
        super().__init__(EvalConfigChangeSet, db_session_factory)

    async def get_by_config_version(
        self, config_version_id: str, skip: int = 0, limit: int = 100
    ) -> List[EvalConfigChangeSet]:
        """查询指定配置版本的所有变更集"""
        return await self.get_by_filter(
            config_version_id=config_version_id,
            skip=skip,
            limit=limit,
            order_by=desc(EvalConfigChangeSet.created_at),
        )

    async def get_by_status(
        self, status: str, skip: int = 0, limit: int = 100
    ) -> List[EvalConfigChangeSet]:
        """根据状态查询变更集"""
        return await self.get_by_filter(
            status=status,
            skip=skip,
            limit=limit,
            order_by=desc(EvalConfigChangeSet.created_at),
        )

    async def get_committed_by_version(
        self, config_version_id: str
    ) -> List[EvalConfigChangeSet]:
        """查询指定配置版本的已提交变更集"""
        return await self.get_by_filter(
            config_version_id=config_version_id,
            status="committed",
            order_by=desc(EvalConfigChangeSet.created_at),
        )
