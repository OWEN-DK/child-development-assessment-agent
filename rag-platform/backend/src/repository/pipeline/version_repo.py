"""管道版本 Repository"""
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from src.models.pipeline_version import PipelineVersion
from src.repository.base import BaseRepository


class PipelineVersionRepository(BaseRepository[PipelineVersion]):
    """管道版本数据访问层"""

    def __init__(self, db_session_factory: async_sessionmaker):
        super().__init__(PipelineVersion, db_session_factory)

    async def list_by_pipeline(
        self, pipeline_id: str, tenant_id: str
    ) -> list[PipelineVersion]:
        """列出管道的所有版本"""
        async with self.db_session_factory() as session:
            stmt = select(PipelineVersion).where(
                PipelineVersion.pipeline_id == pipeline_id,
                PipelineVersion.tenant_id == tenant_id,
            ).order_by(PipelineVersion.version_number.desc())
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def get_by_version(
        self, pipeline_id: str, version_number: int, tenant_id: str
    ) -> Optional[PipelineVersion]:
        """获取指定版本"""
        async with self.db_session_factory() as session:
            stmt = select(PipelineVersion).where(
                PipelineVersion.pipeline_id == pipeline_id,
                PipelineVersion.version_number == version_number,
                PipelineVersion.tenant_id == tenant_id,
            )
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def get_latest(
        self, pipeline_id: str, tenant_id: str
    ) -> Optional[PipelineVersion]:
        """获取最新版本"""
        async with self.db_session_factory() as session:
            stmt = select(PipelineVersion).where(
                PipelineVersion.pipeline_id == pipeline_id,
                PipelineVersion.tenant_id == tenant_id,
            ).order_by(PipelineVersion.version_number.desc()).limit(1)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def get_next_version_number(
        self, pipeline_id: str, tenant_id: str
    ) -> int:
        """获取下一个版本号"""
        latest = await self.get_latest(pipeline_id, tenant_id)
        return (latest.version_number + 1) if latest else 1
