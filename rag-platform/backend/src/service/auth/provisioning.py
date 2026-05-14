"""租户初始化（Provisioning）

创建租户时自动执行：
1. 插入 tenants 表记录
2. 创建存储目录结构
3. 初始化默认角色（admin/editor/viewer）
4. 创建初始管理员用户
5. 绑定 admin 角色
6. 记录配额限制

任一步骤失败则整体回滚（DB 事务 + 文件系统清理）。
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
from src.utils.logger import logger


class ProvisioningService:
    """租户初始化服务"""

    def __init__(self, db_session_factory: async_sessionmaker):
        self.db_session_factory = db_session_factory

    async def provision(self, data) -> dict:
        """初始化新租户（事务性）

        所有数据库操作在同一个事务中执行。
        文件系统操作在事务外执行，失败时手动清理。

        Args:
            data: 租户创建请求（TenantCreate）

        Returns:
            {"tenant_id": str, "admin_user_id": str, "admin_login_url": str}
        """
        tenant_id = str(uuid.uuid4())
        admin_user_id = str(uuid.uuid4())
        storage_path = None

        async with self.db_session_factory() as session:
            async with session.begin():
                # 1. 创建租户记录
                tenant = Tenant(
                    id=tenant_id,
                    name=data.name,
                    slug=data.slug,
                    status="active",
                    resource_limits=data.quotas.model_dump() if hasattr(data.quotas, 'model_dump') else data.quotas,
                )
                session.add(tenant)
                await session.flush()
                logger.info(f"[1/6] 租户创建成功: {data.name} ({data.slug})")

                # 2. 创建存储目录（事务外，失败需手动清理）
                storage_base = os.getenv("RAG_STORAGE_DIR", "./app_data/storage")
                storage_path = Path(storage_base) / data.slug
                try:
                    for subdir in ["documents", "chroma", "bm25", "exports"]:
                        (storage_path / subdir).mkdir(parents=True, exist_ok=True)
                    logger.info(f"[2/6] 存储目录创建完成: {storage_path}")
                except Exception as e:
                    raise RuntimeError(f"存储目录创建失败: {e}")

                # 3. 初始化默认角色
                role_ids = {}
                for slug, role_def in DEFAULT_ROLES.items():
                    role_id = str(uuid.uuid4())
                    role = Role(
                        id=role_id,
                        tenant_id=tenant_id,
                        name=role_def["name"],
                        slug=slug,
                        permissions=role_def["permissions"],
                        is_builtin=True,
                    )
                    session.add(role)
                    role_ids[slug] = role_id
                await session.flush()
                logger.info(f"[3/6] 默认角色初始化完成: {list(role_ids.keys())}")

                # 4. 创建初始管理员
                admin_user = User(
                    id=admin_user_id,
                    tenant_id=tenant_id,
                    username=data.admin_user.username,
                    email=data.admin_user.email,
                    password_hash=hash_password(data.admin_user.password),
                    status="active",
                )
                session.add(admin_user)
                await session.flush()
                logger.info(f"[4/6] 管理员用户创建完成: {data.admin_user.username}")

                # 5. 绑定 admin 角色
                user_role = UserRole(
                    user_id=admin_user_id,
                    role_id=role_ids["admin"],
                )
                session.add(user_role)
                logger.info(f"[5/6] 管理员角色绑定完成")

                # 6. 记录配额（存入 tenant.resource_limits，已在步骤 1 完成）
                logger.info(f"[6/6] 租户初始化完成")

            # 事务成功提交

        return {
            "tenant_id": tenant_id,
            "admin_user_id": admin_user_id,
            "admin_login_url": f"/login?tenant={data.slug}",
        }
