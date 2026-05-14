"""审计日志数据访问层"""
from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from src.models.audit import (
    GodModeAuditLog,
    PermissionAuditLog,
    TenantAuditLog,
    TenantDeletionSnapshot,
)
from src.repository.base import BaseRepository


class AuditRepository:
    """审计日志统一 Repository"""

    def __init__(self, db_session_factory: async_sessionmaker):
        self.db_session_factory = db_session_factory

    async def log_god_mode_action(
        self,
        tenant_id: str,
        actor_id: str,
        action: str,
        target_type: str | None = None,
        target_id: str | None = None,
        details: str | None = None,
        session_started_at: datetime | None = None,
    ) -> GodModeAuditLog:
        """记录 God Mode 操作"""
        async with self.db_session_factory() as session:
            log = GodModeAuditLog(
                tenant_id=tenant_id,
                actor_id=actor_id,
                action=action,
                target_type=target_type,
                target_id=target_id,
                details=details,
                session_started_at=session_started_at,
            )
            session.add(log)
            await session.commit()
            return log

    async def log_permission_change(
        self,
        tenant_id: str,
        actor_id: str,
        action: str,
        target_type: str,
        target_id: str,
        old_value: dict | None = None,
        new_value: dict | None = None,
    ) -> PermissionAuditLog:
        """记录权限变更"""
        async with self.db_session_factory() as session:
            log = PermissionAuditLog(
                tenant_id=tenant_id,
                actor_id=actor_id,
                action=action,
                target_type=target_type,
                target_id=target_id,
                old_value=old_value,
                new_value=new_value,
            )
            session.add(log)
            await session.commit()
            return log

    async def log_tenant_action(
        self,
        tenant_id: str,
        actor_id: str,
        action: str,
        details: str | None = None,
    ) -> TenantAuditLog:
        """记录租户操作"""
        async with self.db_session_factory() as session:
            log = TenantAuditLog(
                tenant_id=tenant_id,
                actor_id=actor_id,
                action=action,
                details=details,
            )
            session.add(log)
            await session.commit()
            return log

    async def get_god_mode_logs(
        self, tenant_id: str, skip: int = 0, limit: int = 100
    ) -> list[GodModeAuditLog]:
        """获取 God Mode 审计日志"""
        async with self.db_session_factory() as session:
            result = await session.execute(
                select(GodModeAuditLog)
                .where(GodModeAuditLog.tenant_id == tenant_id)
                .order_by(GodModeAuditLog.created_at.desc())
                .offset(skip)
                .limit(limit)
            )
            return list(result.scalars().all())

    async def count_god_mode_logs(self, tenant_id: str) -> int:
        """统计 God Mode 审计日志数"""
        from sqlalchemy import func

        async with self.db_session_factory() as session:
            result = await session.execute(
                select(func.count())
                .select_from(GodModeAuditLog)
                .where(GodModeAuditLog.tenant_id == tenant_id)
            )
            return result.scalar() or 0
