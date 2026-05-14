"""用户数据访问层"""
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from src.models.user import User, UserRole
from src.repository.base import BaseRepository


class UserRepository(BaseRepository[User]):
    """用户 Repository"""

    def __init__(self, db_session_factory: async_sessionmaker):
        super().__init__(User, db_session_factory)

    async def find_by_email(self, email: str, tenant_id: str | None = None) -> Optional[User]:
        """根据邮箱查找用户"""
        async with self.db_session_factory() as session:
            stmt = select(User).where(User.email == email)
            if tenant_id is not None:
                stmt = stmt.where(User.tenant_id == tenant_id)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def find_by_username(self, username: str, tenant_id: str) -> Optional[User]:
        """根据用户名查找用户"""
        async with self.db_session_factory() as session:
            result = await session.execute(
                select(User).where(
                    User.username == username,
                    User.tenant_id == tenant_id,
                )
            )
            return result.scalar_one_or_none()

    async def find_superadmin(self, username: str) -> Optional[User]:
        """查找超管用户"""
        async with self._get_admin_session() as session:
            result = await session.execute(
                select(User).where(
                    User.username == username,
                    User.tenant_id.is_(None),
                )
            )
            return result.scalar_one_or_none()

    async def list_by_tenant(self, tenant_id: str, skip: int = 0, limit: int = 100) -> list[User]:
        """列出租户下的用户"""
        return await self.get_by_filter(
            tenant_id=tenant_id,
            skip=skip,
            limit=limit,
            status="active",
        )

    async def count_by_tenant(self, tenant_id: str) -> int:
        """统计租户下的用户数"""
        return await self.count(tenant_id=tenant_id)


class UserRoleRepository:
    """用户角色关联 Repository"""

    def __init__(self, db_session_factory: async_sessionmaker):
        self.db_session_factory = db_session_factory

    async def assign_role(self, user_id: str, role_id: str) -> UserRole:
        """分配角色"""
        async with self.db_session_factory() as session:
            user_role = UserRole(user_id=user_id, role_id=role_id)
            session.add(user_role)
            await session.commit()
            return user_role

    async def remove_role(self, user_id: str, role_id: str) -> bool:
        """移除角色"""
        from sqlalchemy import delete

        async with self.db_session_factory() as session:
            result = await session.execute(
                delete(UserRole).where(
                    UserRole.user_id == user_id,
                    UserRole.role_id == role_id,
                )
            )
            await session.commit()
            return result.rowcount > 0

    async def get_roles_by_user(self, user_id: str) -> list[str]:
        """获取用户的角色 ID 列表"""
        async with self.db_session_factory() as session:
            result = await session.execute(
                select(UserRole.role_id).where(UserRole.user_id == user_id)
            )
            return [row[0] for row in result.all()]

    async def remove_all_roles(self, user_id: str) -> bool:
        """移除用户的所有角色"""
        from sqlalchemy import delete

        async with self.db_session_factory() as session:
            result = await session.execute(
                delete(UserRole).where(UserRole.user_id == user_id)
            )
            await session.commit()
            return result.rowcount > 0
