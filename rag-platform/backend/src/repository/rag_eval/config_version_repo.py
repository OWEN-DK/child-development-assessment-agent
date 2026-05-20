"""评估配置版本 Repository"""
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from src.models.rag_eval.config_version import EvalConfigChangeSet, EvalConfigVersion
from src.repository.base import BaseRepository
from src.utils.exceptions import ResourceNotFoundException


class ConfigVersionRepository(BaseRepository[EvalConfigVersion]):
    """评估配置版本数据访问层"""

    def __init__(self, db_session_factory: async_sessionmaker):
        super().__init__(EvalConfigVersion, db_session_factory)

    async def list(self, tenant_id: str) -> list[EvalConfigVersion]:
        """查询租户下所有配置版本（按版本号降序）"""
        async with self.db_session_factory() as session:
            stmt = (
                select(EvalConfigVersion)
                .where(EvalConfigVersion.tenant_id == tenant_id)
                .order_by(EvalConfigVersion.version_number.desc())
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def get_by_id(self, id: str, tenant_id: Optional[str] = None) -> Optional[EvalConfigVersion]:
        """根据 ID 查询单个配置版本"""
        async with self.db_session_factory() as session:
            stmt = select(EvalConfigVersion).where(EvalConfigVersion.id == id)
            if tenant_id is not None:
                stmt = stmt.where(EvalConfigVersion.tenant_id == tenant_id)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def create(self, obj_data: Dict[str, Any]) -> EvalConfigVersion:
        """创建配置版本"""
        return await super().create(obj_data)

    async def get_latest(self, tenant_id: str) -> Optional[EvalConfigVersion]:
        """获取租户最新的配置版本"""
        async with self.db_session_factory() as session:
            stmt = (
                select(EvalConfigVersion)
                .where(EvalConfigVersion.tenant_id == tenant_id)
                .order_by(EvalConfigVersion.version_number.desc())
                .limit(1)
            )
            result = await session.execute(stmt)
            return result.scalar_one_or_none()


class ConfigChangeSetRepository(BaseRepository[EvalConfigChangeSet]):
    """评估配置变更集数据访问层"""

    def __init__(self, db_session_factory: async_sessionmaker):
        super().__init__(EvalConfigChangeSet, db_session_factory)

    async def create(self, obj_data: Dict[str, Any]) -> EvalConfigChangeSet:
        """创建变更集"""
        return await super().create(obj_data)

    async def update_status(
        self,
        id: str,
        status: str,
        reason: Optional[str] = None,
        tenant_id: Optional[str] = None,
    ) -> EvalConfigChangeSet:
        """更新变更集状态

        Args:
            id: 变更集 ID
            status: 目标状态（committed/rolled_back）
            reason: 回滚原因（仅 rolled_back 时有意义）
            tenant_id: 租户 ID
        """
        async with self.db_session_factory() as session:
            stmt = select(EvalConfigChangeSet).where(EvalConfigChangeSet.id == id)
            if tenant_id is not None:
                stmt = stmt.where(EvalConfigChangeSet.tenant_id == tenant_id)
            result = await session.execute(stmt)
            change_set = result.scalar_one_or_none()
            if change_set is None:
                raise ResourceNotFoundException(message=f"EvalConfigChangeSet not found: id={id}")
            change_set.status = status
            if reason is not None:
                change_set.rollback_reason = reason
            await session.commit()
            await session.refresh(change_set)
            return change_set
