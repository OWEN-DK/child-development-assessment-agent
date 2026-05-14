"""租户数据访问层"""
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from src.models.tenant import Tenant
from src.repository.base import BaseRepository


class TenantRepository(BaseRepository[Tenant]):
    """租户 Repository"""

    def __init__(self, db_session_factory: async_sessionmaker):
        super().__init__(Tenant, db_session_factory)

    async def find_by_slug(self, slug: str) -> Optional[Tenant]:
        """根据 slug 查找租户"""
        async with self._get_admin_session() as session:
            result = await session.execute(
                select(Tenant).where(Tenant.slug == slug)
            )
            return result.scalar_one_or_none()

    async def list_active(self, skip: int = 0, limit: int = 100) -> list[Tenant]:
        """列出所有活跃租户"""
        return await self.get_by_filter(
            tenant_id=None,  # 超管操作，不过滤
            skip=skip,
            limit=limit,
            status="active",
        )

    async def list_all_admin(self, skip: int = 0, limit: int = 100) -> list[Tenant]:
        """列出所有租户（超管专用，含停用/归档）"""
        async with self._get_admin_session() as session:
            result = await session.execute(
                select(Tenant)
                .where(Tenant.deleted_at.is_(None))
                .offset(skip)
                .limit(limit)
                .order_by(Tenant.created_at.desc())
            )
            return list(result.scalars().all())

    async def soft_delete(self, tenant_id: str) -> bool:
        """软删除租户"""
        from datetime import datetime
        result = await self.update(
            obj_id=tenant_id,
            obj_data={"status": "deleted", "deleted_at": datetime.utcnow()},
            tenant_id=None,  # 超管操作
        )
        return result is not None

    async def restore(self, tenant_id: str) -> bool:
        """恢复已删除/归档的租户"""
        result = await self.update(
            obj_id=tenant_id,
            obj_data={"status": "active", "deleted_at": None},
            tenant_id=None,
        )
        return result is not None
