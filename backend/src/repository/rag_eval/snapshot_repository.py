from typing import List

from sqlalchemy import desc
from sqlalchemy.ext.asyncio import async_sessionmaker

from src.core.database import async_session_factory as _default_session_factory
from src.models.rag_eval.snapshot import KnowledgeSnapshot
from src.repository.base import BaseRepository


class SnapshotRepository(BaseRepository[KnowledgeSnapshot]):
    def __init__(self, db_session_factory: async_sessionmaker = _default_session_factory):
        super().__init__(KnowledgeSnapshot, db_session_factory)

    async def get_by_config_version(
        self, config_version_id: str
    ) -> List[KnowledgeSnapshot]:
        """根据配置版本 ID 查询快照"""
        return await self.get_by_filter(
            config_version_id=config_version_id,
            order_by=desc(KnowledgeSnapshot.created_at),
        )

    async def get_latest_snapshots(self, limit: int = 10) -> List[KnowledgeSnapshot]:
        """获取最近知识库快照"""
        return await self.get_all(
            limit=limit,
            order_by=desc(KnowledgeSnapshot.created_at),
        )
