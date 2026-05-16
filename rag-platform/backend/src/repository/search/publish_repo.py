"""发布端点 Repository"""
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from src.models.published_endpoint import PublishedEndpoint
from src.repository.base import BaseRepository


class PublishedEndpointRepository(BaseRepository[PublishedEndpoint]):
    """发布端点数据访问层"""

    def __init__(self, db_session_factory: async_sessionmaker):
        super().__init__(PublishedEndpoint, db_session_factory)

    async def get_by_url_path(self, url_path: str) -> Optional[PublishedEndpoint]:
        """根据 URL 路径查询端点（全局查询，无租户过滤）"""
        async with self._get_admin_session() as session:
            stmt = select(PublishedEndpoint).where(
                PublishedEndpoint.url_path == url_path
            )
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def get_by_pipeline_id(
        self, pipeline_id: str, tenant_id: str
    ) -> Optional[PublishedEndpoint]:
        """根据管道ID查询端点"""
        async with self._get_session(tenant_id) as session:
            stmt = select(PublishedEndpoint).where(
                PublishedEndpoint.pipeline_id == pipeline_id,
                PublishedEndpoint.tenant_id == tenant_id,
            )
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def list_enabled(self) -> list[PublishedEndpoint]:
        """列出所有启用的端点（启动时加载，无租户过滤）"""
        async with self._get_admin_session() as session:
            stmt = select(PublishedEndpoint).where(
                PublishedEndpoint.enabled == 1
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def list_by_tenant(
        self,
        tenant_id: str,
        page: int = 1,
        page_size: int = 20,
        enabled_only: Optional[bool] = None,
        keyword: Optional[str] = None,
    ) -> tuple[list[PublishedEndpoint], int]:
        """分页查询租户的端点列表

        Returns:
            (端点列表, 总数)
        """
        async with self._get_session(tenant_id) as session:
            stmt = select(PublishedEndpoint).where(
                PublishedEndpoint.tenant_id == tenant_id
            )

            if enabled_only is not None:
                stmt = stmt.where(PublishedEndpoint.enabled == (1 if enabled_only else 0))

            if keyword:
                stmt = stmt.where(PublishedEndpoint.url_path.ilike(f"%{keyword}%"))

            # 统计总数
            count_stmt = select(func.count()).select_from(stmt.subquery())
            total = (await session.execute(count_stmt)).scalar() or 0

            # 分页
            stmt = stmt.order_by(PublishedEndpoint.created_at.desc())
            stmt = stmt.offset((page - 1) * page_size).limit(page_size)
            result = await session.execute(stmt)
            return list(result.scalars().all()), total

    async def check_url_path_conflict(self, url_path: str) -> bool:
        """检查 URL 路径是否已被占用（全局唯一）"""
        async with self._get_admin_session() as session:
            stmt = select(func.count()).select_from(PublishedEndpoint).where(
                PublishedEndpoint.url_path == url_path
            )
            count = (await session.execute(stmt)).scalar() or 0
            return count > 0
