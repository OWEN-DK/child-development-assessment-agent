"""调优建议 Repository"""
from typing import Any, Dict, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from src.models.rag_eval.tuning import TuningSuggestion
from src.repository.base import BaseRepository
from src.utils.exceptions import ResourceNotFoundException


class TuningSuggestionRepository(BaseRepository[TuningSuggestion]):
    """调优建议数据访问层"""

    def __init__(self, db_session_factory: async_sessionmaker):
        super().__init__(TuningSuggestion, db_session_factory)

    async def list_by_run(self, run_id: str) -> list[TuningSuggestion]:
        """查询某次运行的所有调优建议"""
        async with self.db_session_factory() as session:
            stmt = (
                select(TuningSuggestion)
                .where(TuningSuggestion.run_id == run_id)
                .order_by(TuningSuggestion.priority.desc(), TuningSuggestion.created_at)
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def get_by_id(self, id: str, tenant_id: Optional[str] = None) -> Optional[TuningSuggestion]:
        """根据 ID 查询单个建议"""
        async with self.db_session_factory() as session:
            stmt = select(TuningSuggestion).where(TuningSuggestion.id == id)
            if tenant_id is not None:
                stmt = stmt.where(TuningSuggestion.tenant_id == tenant_id)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def create(self, obj_data: Dict[str, Any]) -> TuningSuggestion:
        """创建调优建议"""
        return await super().create(obj_data)

    async def update_status(
        self,
        id: str,
        status: str,
        applied_version_id: Optional[str] = None,
    ) -> TuningSuggestion:
        """更新建议状态

        Args:
            id: 建议 ID
            status: 目标状态（pending/adopted/rejected/ignored）
            applied_version_id: 采纳时关联的配置版本ID
        """
        async with self.db_session_factory() as session:
            stmt = select(TuningSuggestion).where(TuningSuggestion.id == id)
            result = await session.execute(stmt)
            suggestion = result.scalar_one_or_none()
            if suggestion is None:
                raise ResourceNotFoundException(message=f"TuningSuggestion not found: id={id}")
            suggestion.status = status
            if applied_version_id is not None:
                suggestion.applied_config_version_id = applied_version_id
            await session.commit()
            await session.refresh(suggestion)
            return suggestion
