"""评估报告 Repository"""
from typing import Any, Dict, List, Optional

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from src.models.rag_eval.eval_report import EvalReport
from src.repository.base import BaseRepository


class ReportRepository(BaseRepository[EvalReport]):
    """评估报告数据访问层"""

    def __init__(self, db_session_factory: async_sessionmaker):
        super().__init__(EvalReport, db_session_factory)

    async def list_reports(
        self,
        tenant_id: str,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[EvalReport], int]:
        """分页查询评估报告

        Returns:
            (报告列表, 总数)
        """
        async with self.db_session_factory() as session:
            where = EvalReport.tenant_id == tenant_id

            count_stmt = select(func.count()).select_from(EvalReport).where(where)
            total = (await session.execute(count_stmt)).scalar() or 0

            stmt = (
                select(EvalReport)
                .where(where)
                .order_by(EvalReport.created_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
            result = await session.execute(stmt)
            return list(result.scalars().all()), total

    async def get_by_id(self, id: str, tenant_id: Optional[str] = None) -> Optional[EvalReport]:
        """根据 ID 查询单个报告"""
        async with self.db_session_factory() as session:
            stmt = select(EvalReport).where(EvalReport.id == id)
            if tenant_id is not None:
                stmt = stmt.where(EvalReport.tenant_id == tenant_id)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def get_by_run_id(self, run_id: str, tenant_id: Optional[str] = None) -> Optional[EvalReport]:
        """根据运行ID查询关联报告"""
        async with self.db_session_factory() as session:
            stmt = select(EvalReport).where(EvalReport.run_id == run_id)
            if tenant_id is not None:
                stmt = stmt.where(EvalReport.tenant_id == tenant_id)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def create(self, obj_data: Dict[str, Any]) -> EvalReport:
        """创建评估报告"""
        return await super().create(obj_data)

    async def update(self, id: str, obj_data: Dict[str, Any], tenant_id: Optional[str] = None) -> EvalReport:
        """更新评估报告"""
        return await super().update(id, obj_data, tenant_id)

    async def delete(self, id: Any, tenant_id: Optional[str] = None) -> bool:
        """删除评估报告"""
        return await super().delete(id, tenant_id)

    async def batch_delete(self, ids: List[str], tenant_id: Optional[str] = None) -> int:
        """批量删除评估报告

        Returns:
            实际删除的行数
        """
        async with self.db_session_factory() as session:
            stmt = delete(EvalReport).where(EvalReport.id.in_(ids))
            if tenant_id is not None:
                stmt = stmt.where(EvalReport.tenant_id == tenant_id)
            result = await session.execute(stmt)
            await session.commit()
            return result.rowcount
