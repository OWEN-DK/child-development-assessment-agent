"""角色管理服务"""
import uuid

from sqlalchemy.ext.asyncio import async_sessionmaker

from src.core.auth.exceptions import AuthorizationError, RoleNotFoundError
from src.core.auth.defaults import PERMISSION_SET
from src.repository.auth.role_repo import RoleRepository
from src.repository.auth.audit_repo import AuditRepository
from src.schemas.auth.role import RoleCreate, RoleRead, RoleUpdate, RoleList, PermissionItem, PermissionList
from src.utils.logger import logger


class RoleService:
    """角色服务"""

    def __init__(self, db_session_factory: async_sessionmaker):
        self.db_session_factory = db_session_factory
        self.role_repo = RoleRepository(db_session_factory)
        self.audit_repo = AuditRepository(db_session_factory)

    async def create(
        self, tenant_id: str, data: RoleCreate, creator_roles: list[str], actor_id: str
    ) -> RoleRead:
        """创建角色（权限不能超出创建者自身权限）"""
        # 检查权限范围
        if "*" not in creator_roles:
            for perm in data.permissions:
                if perm not in creator_roles and perm != "*":
                    raise AuthorizationError(
                        message=f"无权授予权限: {perm}"
                    )

        role_data = {
            "id": str(uuid.uuid4()),
            "tenant_id": tenant_id,
            "name": data.name,
            "slug": data.name.lower().replace(" ", "_"),
            "permissions": data.permissions,
            "is_builtin": False,
        }
        role = await self.role_repo.create(role_data)

        await self.audit_repo.log_permission_change(
            tenant_id=tenant_id,
            actor_id=actor_id,
            action="create_role",
            target_type="role",
            target_id=role.id,
            new_value={"name": data.name, "permissions": data.permissions},
        )

        return await self._to_read(role)

    async def get(self, role_id: str, tenant_id: str) -> RoleRead:
        """获取角色详情"""
        role = await self.role_repo.get_by_id(role_id, tenant_id=tenant_id)
        if role is None:
            raise RoleNotFoundError(message=f"角色 {role_id} 不存在")
        return await self._to_read(role)

    async def list(self, tenant_id: str, skip: int = 0, limit: int = 100) -> RoleList:
        """列出租户下的角色"""
        roles = await self.role_repo.list_by_tenant(tenant_id, skip=skip, limit=limit)
        total = await self.role_repo.count(tenant_id=tenant_id)
        items = [await self._to_read(r) for r in roles]
        return RoleList(items=items, total=total)

    async def update(
        self, role_id: str, tenant_id: str, data: RoleUpdate, actor_id: str
    ) -> RoleRead:
        """更新角色"""
        role = await self.role_repo.get_by_id(role_id, tenant_id=tenant_id)
        if role is None:
            raise RoleNotFoundError(message=f"角色 {role_id} 不存在")

        if role.is_builtin:
            raise AuthorizationError(message="内置角色不可修改")

        update_data = data.model_dump(exclude_unset=True)
        if update_data:
            await self.role_repo.update(role_id, update_data, tenant_id=tenant_id)
            await self.audit_repo.log_permission_change(
                tenant_id=tenant_id,
                actor_id=actor_id,
                action="update_role",
                target_type="role",
                target_id=role_id,
                new_value=update_data,
            )

        return await self.get(role_id, tenant_id)

    async def delete(self, role_id: str, tenant_id: str, actor_id: str) -> None:
        """删除角色"""
        role = await self.role_repo.get_by_id(role_id, tenant_id=tenant_id)
        if role is None:
            raise RoleNotFoundError(message=f"角色 {role_id} 不存在")

        if role.is_builtin:
            raise AuthorizationError(message="内置角色不可删除")

        # 检查是否有用户引用
        if await self.role_repo.check_role_in_use(role_id):
            raise AuthorizationError(message="该角色仍有用户引用，无法删除")

        await self.role_repo.delete(role_id, tenant_id=tenant_id)
        await self.audit_repo.log_permission_change(
            tenant_id=tenant_id,
            actor_id=actor_id,
            action="delete_role",
            target_type="role",
            target_id=role_id,
        )

    def get_permissions(self) -> PermissionList:
        """获取所有可用权限"""
        items = [
            PermissionItem(
                permission_code=code,
                category=code.split(":")[0] if ":" in code else "other",
                description=desc,
            )
            for code, desc in PERMISSION_SET.items()
        ]
        return PermissionList(permissions=items)

    async def _to_read(self, role) -> RoleRead:
        """转换为读取模型"""
        user_count = await self.role_repo.count_users_by_role(role.id)
        return RoleRead(
            id=role.id,
            name=role.name,
            slug=role.slug,
            permissions=role.permissions,
            is_builtin=role.is_builtin,
            user_count=user_count,
            created_at=role.created_at,
        )
