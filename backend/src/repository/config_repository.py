from typing import List, Optional

from sqlalchemy import desc, or_, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from src.models.config import ConfigAuditLog, ConfigVersion
from src.repository.base import BaseRepository


class ConfigVersionRepository(BaseRepository[ConfigVersion]):
    def __init__(self, db_session_factory: async_sessionmaker):
        super().__init__(ConfigVersion, db_session_factory)

    async def get_latest_version(self) -> Optional[ConfigVersion]:
        """获取最新配置版本（按创建时间排序）

        注意: ConfigVersion没有key字段，直接取最新版本
        """
        async with self.db_session_factory() as session:
            result = await session.execute(
                select(ConfigVersion).order_by(desc(ConfigVersion.created_at)).limit(1)
            )
            return result.scalar_one_or_none()

    async def get_version_history(
        self, skip: int = 0, limit: int = 20
    ) -> List[ConfigVersion]:
        """获取配置版本历史"""
        return await self.get_by_filter(
            skip=skip, limit=limit, order_by=desc(ConfigVersion.created_at)
        )

    async def get_by_parent_version(
        self, parent_version_id: str
    ) -> List[ConfigVersion]:
        """获取指定父版本的子版本"""
        return await self.get_by_filter(parent_version_id=parent_version_id)


class ConfigAuditLogRepository(BaseRepository[ConfigAuditLog]):
    def __init__(self, db_session_factory: async_sessionmaker):
        super().__init__(ConfigAuditLog, db_session_factory)

    async def get_logs_by_version(self, version_id: str) -> List[ConfigAuditLog]:
        """获取指定版本相关的审计日志（包含from_version和to_version）"""
        async with self.db_session_factory() as session:
            result = await session.execute(
                select(ConfigAuditLog)
                .where(
                    or_(
                        ConfigAuditLog.from_version == version_id,
                        ConfigAuditLog.to_version == version_id,
                    )
                )
                .order_by(desc(ConfigAuditLog.timestamp))
            )
            return list(result.scalars().all())

    async def get_logs_by_action(
        self, action: str, skip: int = 0, limit: int = 50
    ) -> List[ConfigAuditLog]:
        """根据操作类型获取审计日志"""
        return await self.get_by_filter(
            skip=skip,
            limit=limit,
            order_by=desc(ConfigAuditLog.timestamp),
            action=action,
        )
