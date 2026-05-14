"""租户 CRUD + 生命周期管理

状态机：active ⇄ disabled ⇄ archived ⇄ deleted
"""
from datetime import datetime
from typing import Optional

from sqlalchemy.ext.asyncio import async_sessionmaker

from src.core.auth.exceptions import TenantNotFoundError
from src.repository.auth.tenant_repo import TenantRepository
from src.repository.auth.audit_repo import AuditRepository
from src.schemas.auth.tenant import TenantCreate, TenantRead, TenantUpdate, TenantList
from src.service.auth.provisioning import ProvisioningService
from src.utils.logger import logger


class TenantService:
    """租户服务"""

    def __init__(self, db_session_factory: async_sessionmaker):
        self.db_session_factory = db_session_factory
        self.tenant_repo = TenantRepository(db_session_factory)
        self.audit_repo = AuditRepository(db_session_factory)
        self.provisioning = ProvisioningService(db_session_factory)

    async def create(self, data: TenantCreate, actor_id: str) -> TenantRead:
        """创建租户（含初始化）"""
        result = await self.provisioning.provision(data)
        tenant = await self.tenant_repo.get_by_id(result["tenant_id"])

        # 记录审计日志
        await self.audit_repo.log_tenant_action(
            tenant_id=result["tenant_id"],
            actor_id=actor_id,
            action="create",
            details=f"创建租户: {data.name} ({data.slug})",
        )

        return self._to_read(tenant)

    async def get(self, tenant_id: str) -> TenantRead:
        """获取租户详情"""
        tenant = await self.tenant_repo.get_by_id(tenant_id)
        if tenant is None:
            raise TenantNotFoundError(message=f"租户 {tenant_id} 不存在")
        return self._to_read(tenant)

    async def list(self, skip: int = 0, limit: int = 100) -> TenantList:
        """列出所有租户"""
        tenants = await self.tenant_repo.list_all_admin(skip=skip, limit=limit)
        total = await self.tenant_repo.count()
        return TenantList(
            items=[self._to_read(t) for t in tenants],
            total=total,
        )

    async def update(self, tenant_id: str, data: TenantUpdate, actor_id: str) -> TenantRead:
        """更新租户"""
        update_data = data.model_dump(exclude_unset=True)
        if not update_data:
            return await self.get(tenant_id)

        tenant = await self.tenant_repo.update(tenant_id, update_data)
        if tenant is None:
            raise TenantNotFoundError(message=f"租户 {tenant_id} 不存在")

        await self.audit_repo.log_tenant_action(
            tenant_id=tenant_id,
            actor_id=actor_id,
            action="update",
            details=f"更新租户: {update_data}",
        )

        return self._to_read(tenant)

    async def disable(self, tenant_id: str, actor_id: str) -> TenantRead:
        """停用租户"""
        tenant = await self.tenant_repo.update(
            obj_id=tenant_id,
            obj_data={"status": "disabled"},
            tenant_id=None,
        )
        await self.audit_repo.log_tenant_action(
            tenant_id=tenant_id,
            actor_id=actor_id,
            action="disable",
        )
        return self._to_read(tenant)

    async def archive(self, tenant_id: str, actor_id: str) -> TenantRead:
        """归档租户"""
        tenant = await self.tenant_repo.update(
            obj_id=tenant_id,
            obj_data={"status": "archived"},
            tenant_id=None,
        )
        await self.audit_repo.log_tenant_action(
            tenant_id=tenant_id,
            actor_id=actor_id,
            action="archive",
        )
        return self._to_read(tenant)

    async def restore(self, tenant_id: str, actor_id: str) -> TenantRead:
        """恢复租户"""
        await self.tenant_repo.restore(tenant_id)
        tenant = await self.tenant_repo.get_by_id(tenant_id)
        await self.audit_repo.log_tenant_action(
            tenant_id=tenant_id,
            actor_id=actor_id,
            action="restore",
        )
        return self._to_read(tenant)

    async def soft_delete(self, tenant_id: str, actor_id: str) -> None:
        """软删除租户（30 天保留期）"""
        await self.tenant_repo.soft_delete(tenant_id)
        await self.audit_repo.log_tenant_action(
            tenant_id=tenant_id,
            actor_id=actor_id,
            action="soft_delete",
        )
        logger.info(f"租户 {tenant_id} 已软删除，30 天后物理清理")

    def _to_read(self, tenant) -> TenantRead:
        """转换为读取模型"""
        return TenantRead(
            id=tenant.id,
            name=tenant.name,
            slug=tenant.slug,
            status=tenant.status,
            resource_limits=tenant.resource_limits,
            user_count=0,  # TODO: 实际统计
            storage_usage_gb=0.0,  # TODO: 实际统计
            created_at=tenant.created_at,
            updated_at=tenant.updated_at,
        )
