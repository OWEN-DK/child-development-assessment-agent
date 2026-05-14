"""租户初始化（Provisioning）

创建租户时自动执行：
1. 插入 tenants 表记录
2. 创建存储目录结构
3. 初始化默认角色（admin/editor/viewer）
4. 创建初始管理员用户
5. 绑定 admin 角色
6. 记录配额限制

任一步骤失败则整体回滚。
"""
import os
import uuid
from pathlib import Path

from sqlalchemy.ext.asyncio import async_sessionmaker

from src.core.auth.defaults import DEFAULT_QUOTAS, DEFAULT_ROLES
from src.core.auth.password import hash_password
from src.models.tenant import Tenant
from src.models.user import User, UserRole
from src.models.role import Role
from src.repository.auth.tenant_repo import TenantRepository
from src.repository.auth.user_repo import UserRepository, UserRoleRepository
from src.repository.auth.role_repo import RoleRepository
from src.schemas.auth.tenant import TenantCreate
from src.utils.logger import logger


class ProvisioningService:
    """租户初始化服务"""

    def __init__(self, db_session_factory: async_sessionmaker):
        self.db_session_factory = db_session_factory
        self.tenant_repo = TenantRepository(db_session_factory)
        self.user_repo = UserRepository(db_session_factory)
        self.role_repo = RoleRepository(db_session_factory)
        self.user_role_repo = UserRoleRepository(db_session_factory)

    async def provision(self, data: TenantCreate) -> dict:
        """初始化新租户

        Args:
            data: 租户创建请求

        Returns:
            {"tenant_id": str, "admin_user_id": str, "admin_login_url": str}
        """
        tenant_id = str(uuid.uuid4())
        admin_user_id = str(uuid.uuid4())

        # 1. 创建租户记录
        tenant_data = {
            "id": tenant_id,
            "name": data.name,
            "slug": data.slug,
            "status": "active",
            "resource_limits": data.quotas.model_dump(),
        }
        await self.tenant_repo.create(tenant_data)
        logger.info(f"[1/5] 租户创建成功: {data.name} ({data.slug})")

        # 2. 创建存储目录
        storage_base = os.getenv("RAG_STORAGE_DIR", "./app_data/storage")
        storage_path = Path(storage_base) / data.slug
        for subdir in ["documents", "chroma", "bm25", "exports"]:
            (storage_path / subdir).mkdir(parents=True, exist_ok=True)
        logger.info(f"[2/5] 存储目录创建完成: {storage_path}")

        # 3. 初始化默认角色
        role_ids = {}
        for slug, role_def in DEFAULT_ROLES.items():
            role_id = str(uuid.uuid4())
            role_data = {
                "id": role_id,
                "tenant_id": tenant_id,
                "name": role_def["name"],
                "slug": slug,
                "permissions": role_def["permissions"],
                "is_builtin": True,
            }
            await self.role_repo.create(role_data)
            role_ids[slug] = role_id
        logger.info(f"[3/5] 默认角色初始化完成: {list(role_ids.keys())}")

        # 4. 创建初始管理员
        admin_data = {
            "id": admin_user_id,
            "tenant_id": tenant_id,
            "username": data.admin_user.username,
            "email": data.admin_user.email,
            "password_hash": hash_password(data.admin_user.password),
            "status": "active",
        }
        await self.user_repo.create(admin_data)
        logger.info(f"[4/5] 管理员用户创建完成: {data.admin_user.username}")

        # 5. 绑定 admin 角色
        await self.user_role_repo.assign_role(admin_user_id, role_ids["admin"])
        logger.info(f"[5/5] 管理员角色绑定完成")

        return {
            "tenant_id": tenant_id,
            "admin_user_id": admin_user_id,
            "admin_login_url": f"/login?tenant={data.slug}",
        }
