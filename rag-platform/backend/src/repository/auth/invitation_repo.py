"""邀请数据访问层"""
from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from src.models.invitation import UserInvitation
from src.repository.base import BaseRepository


class InvitationRepository(BaseRepository[UserInvitation]):
    """邀请 Repository"""

    def __init__(self, db_session_factory: async_sessionmaker):
        super().__init__(UserInvitation, db_session_factory)

    async def find_by_token(self, token: str) -> Optional[UserInvitation]:
        """根据令牌查找邀请"""
        async with self._get_admin_session() as session:
            result = await session.execute(
                select(UserInvitation).where(UserInvitation.token == token)
            )
            return result.scalar_one_or_none()

    async def find_pending_by_tenant(self, tenant_id: str) -> list[UserInvitation]:
        """查找租户下的待处理邀请"""
        async with self.db_session_factory() as session:
            result = await session.execute(
                select(UserInvitation).where(
                    UserInvitation.tenant_id == tenant_id,
                    UserInvitation.accepted_at.is_(None),
                    UserInvitation.expires_at > datetime.utcnow(),
                )
            )
            return list(result.scalars().all())

    async def mark_accepted(self, token: str) -> bool:
        """标记邀请已接受"""
        async with self._get_admin_session() as session:
            result = await session.execute(
                select(UserInvitation).where(UserInvitation.token == token)
            )
            invitation = result.scalar_one_or_none()
            if invitation is None:
                return False
            invitation.accepted_at = datetime.utcnow()
            await session.commit()
            return True
