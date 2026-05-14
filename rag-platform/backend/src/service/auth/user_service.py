"""用户管理服务"""
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.ext.asyncio import async_sessionmaker

from src.core.auth.exceptions import (
    InvitationExpiredError,
    InvitationInvalidError,
    UserNotFoundError,
)
from src.core.auth.invitation import InvitationService
from src.core.auth.password import hash_password
from src.repository.auth.user_repo import UserRepository, UserRoleRepository
from src.repository.auth.role_repo import RoleRepository
from src.repository.auth.invitation_repo import InvitationRepository
from src.repository.auth.audit_repo import AuditRepository
from src.schemas.auth.user import UserCreate, UserRead, UserInvite, UserAcceptInvitation, UserUpdate
from src.utils.logger import logger


class UserService:
    """用户服务"""

    def __init__(
        self,
        db_session_factory: async_sessionmaker,
        invitation_service: InvitationService,
    ):
        self.db_session_factory = db_session_factory
        self.user_repo = UserRepository(db_session_factory)
        self.user_role_repo = UserRoleRepository(db_session_factory)
        self.role_repo = RoleRepository(db_session_factory)
        self.invitation_repo = InvitationRepository(db_session_factory)
        self.audit_repo = AuditRepository(db_session_factory)
        self.invitation_service = invitation_service

    async def invite(
        self, tenant_id: str, data: UserInvite, inviter_id: str
    ) -> dict:
        """邀请用户

        Returns:
            {"invitation_id": str, "token": str, "expires_at": datetime}
        """
        import uuid

        # 生成邀请令牌
        token = self.invitation_service.generate_token(
            tenant_id=tenant_id,
            email=data.email,
            roles=data.roles,
        )

        invitation_data = {
            "id": str(uuid.uuid4()),
            "tenant_id": tenant_id,
            "email": data.email,
            "roles": data.roles,
            "token": token,
            "expires_at": datetime.utcnow() + timedelta(hours=24),
            "created_by": inviter_id,
        }
        await self.invitation_repo.create(invitation_data)

        await self.audit_repo.log_permission_change(
            tenant_id=tenant_id,
            actor_id=inviter_id,
            action="invite_user",
            target_type="user",
            target_id=data.email,
            new_value={"roles": data.roles},
        )

        return {
            "invitation_id": invitation_data["id"],
            "token": token,
            "expires_at": invitation_data["expires_at"],
        }

    async def accept_invitation(self, data: UserAcceptInvitation) -> UserRead:
        """接受邀请"""
        # 验证邀请令牌
        payload = self.invitation_service.verify(data.token)

        # 检查邀请是否已接受
        invitation = await self.invitation_repo.find_by_token(data.token)
        if invitation is None:
            raise InvitationInvalidError(message="邀请不存在")
        if invitation.accepted_at is not None:
            raise InvitationInvalidError(message="邀请已被接受")

        # 创建用户
        import uuid
        user_data = {
            "id": str(uuid.uuid4()),
            "tenant_id": payload["tenant_id"],
            "email": payload["email"],
            "username": payload["email"].split("@")[0],  # 用邮箱前缀作为用户名
            "password_hash": hash_password(data.password),
            "status": "active",
        }
        user = await self.user_repo.create(user_data)

        # 分配角色
        for role_name in payload.get("roles", []):
            role = await self.role_repo.find_by_slug(role_name, payload["tenant_id"])
            if role:
                await self.user_role_repo.assign_role(user.id, role.id)

        # 标记邀请已接受
        await self.invitation_repo.mark_accepted(data.token)

        return UserRead(
            id=user.id,
            username=user.username,
            email=user.email,
            status=user.status,
            roles=payload.get("roles", []),
            created_at=user.created_at,
        )

    async def get_user(self, user_id: str, tenant_id: str) -> UserRead:
        """获取用户详情"""
        user = await self.user_repo.get_by_id(user_id, tenant_id=tenant_id)
        if user is None:
            raise UserNotFoundError(message=f"用户 {user_id} 不存在")

        role_ids = await self.user_role_repo.get_roles_by_user(user_id)
        roles = []
        for role_id in role_ids:
            role = await self.role_repo.get_by_id(role_id)
            if role:
                roles.append(role.name)

        return UserRead(
            id=user.id,
            username=user.username,
            email=user.email,
            status=user.status,
            roles=roles,
            created_at=user.created_at,
        )

    async def list_users(self, tenant_id: str, skip: int = 0, limit: int = 100) -> list[UserRead]:
        """列出租户下的用户"""
        users = await self.user_repo.list_by_tenant(tenant_id, skip=skip, limit=limit)
        result = []
        for user in users:
            role_ids = await self.user_role_repo.get_roles_by_user(user.id)
            roles = []
            for role_id in role_ids:
                role = await self.role_repo.get_by_id(role_id)
                if role:
                    roles.append(role.name)
            result.append(UserRead(
                id=user.id,
                username=user.username,
                email=user.email,
                status=user.status,
                roles=roles,
                created_at=user.created_at,
            ))
        return result

    async def update_user(self, user_id: str, tenant_id: str, data: UserUpdate, actor_id: str) -> UserRead:
        """更新用户"""
        update_data = data.model_dump(exclude_unset=True)

        # 更新角色
        if data.roles is not None:
            await self.user_role_repo.remove_all_roles(user_id)
            for role_name in data.roles:
                role = await self.role_repo.find_by_slug(role_name, tenant_id)
                if role:
                    await self.user_role_repo.assign_role(user_id, role.id)

        # 更新状态
        if data.status is not None:
            await self.user_repo.update(user_id, {"status": data.status}, tenant_id=tenant_id)

        return await self.get_user(user_id, tenant_id)

    async def disable_user(self, user_id: str, tenant_id: str, actor_id: str) -> None:
        """禁用用户"""
        await self.user_repo.update(user_id, {"status": "disabled"}, tenant_id=tenant_id)
        await self.audit_repo.log_permission_change(
            tenant_id=tenant_id,
            actor_id=actor_id,
            action="disable_user",
            target_type="user",
            target_id=user_id,
        )
