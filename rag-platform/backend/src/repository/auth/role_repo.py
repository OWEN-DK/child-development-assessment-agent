"""角色数据访问层"""
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import async_sessionmaker

from src.models.role import Role
from src.models.user import UserRole
from src.repository.base import BaseRepository


class RoleRepository(BaseRepository[Role]):
    """角色 Repository"""

    def __init__(self, db_session_factory: async_sessionmaker):
        super().__init__(Role, db_session_factory)

    async def find_by_slug(self, slug: str, tenant_id: str) -> Optional[Role]:
        """根据 slug 查找角色"""
        async with self.db_session_factory() as session:
            result = await session.execute(
                select(Role).where(
                    Role.slug == slug,
                    Role.tenant_id == tenant_id,
                )
            )
            return result.scalar_one_or_none()

    async def list_by_tenant(self, tenant_id: str, skip: int = 0, limit: int = 100) -> list[Role]:
        """列出租户下的角色"""
        return await self.get_by_filter(
            tenant_id=tenant_id,
            skip=skip,
            limit=limit,
        )

    async def count_users_by_role(self, role_id: str) -> int:
        """统计角色下的用户数"""
        async with self.db_session_factory() as session:
            result = await session.execute(
                select(func.count()).select_from(UserRole).where(
                    UserRole.role_id == role_id
                )
            )
            return result.scalar() or 0

    async def check_role_in_use(self, role_id: str) -> bool:
        """检查角色是否被用户引用"""
        count = await self.count_users_by_role(role_id)
        return count > 0
