"""管道 Repository"""
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from src.models.pipeline import Pipeline
from src.repository.base import BaseRepository


class PipelineRepository(BaseRepository[Pipeline]):
    """管道数据访问层"""

    def __init__(self, db_session_factory: async_sessionmaker):
        super().__init__(Pipeline, db_session_factory)

    async def list_by_tenant(
        self,
        tenant_id: str,
        status: Optional[str] = None,
        keyword: Optional[str] = None,
        skip: int = 0,
        limit: int = 20,
    ) -> list[Pipeline]:
        """列出租户的管道"""
        async with self.db_session_factory() as session:
            stmt = select(Pipeline).where(Pipeline.tenant_id == tenant_id)

            if status:
                stmt = stmt.where(Pipeline.status == status)
            if keyword:
                stmt = stmt.where(Pipeline.name.ilike(f"%{keyword}%"))

            stmt = stmt.order_by(Pipeline.updated_at.desc())
            stmt = stmt.offset(skip).limit(limit)

            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def count_by_tenant(self, tenant_id: str) -> int:
        """统计租户的管道数"""
        from sqlalchemy import func

        async with self.db_session_factory() as session:
            stmt = select(func.count()).select_from(Pipeline).where(
                Pipeline.tenant_id == tenant_id
            )
            result = await session.execute(stmt)
            return result.scalar() or 0

    async def update_active_version(
        self, pipeline_id: str, version_number: int, tenant_id: str
    ) -> None:
        """更新活动版本号"""
        async with self.db_session_factory() as session:
            stmt = select(Pipeline).where(
                Pipeline.id == pipeline_id,
                Pipeline.tenant_id == tenant_id,
            )
            result = await session.execute(stmt)
            pipeline = result.scalar_one_or_none()
            if pipeline:
                pipeline.active_version = version_number
                await session.commit()
