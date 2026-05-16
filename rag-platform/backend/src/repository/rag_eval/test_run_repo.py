"""测试运行 Repository"""
from typing import Any, Dict, List, Optional

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from src.models.rag_eval.test_run import TestRun, TestRunResult
from src.repository.base import BaseRepository


class TestRunRepository(BaseRepository[TestRun]):
    """测试运行数据访问层"""

    def __init__(self, db_session_factory: async_sessionmaker):
        super().__init__(TestRun, db_session_factory)

    async def list_runs(
        self,
        tenant_id: str,
        page: int = 1,
        page_size: int = 20,
        pipeline_id: Optional[str] = None,
        status: Optional[str] = None,
    ) -> tuple[list[TestRun], int]:
        """分页查询测试运行，支持管道ID和状态筛选

        Returns:
            (运行列表, 总数)
        """
        async with self.db_session_factory() as session:
            base_where = [TestRun.tenant_id == tenant_id]
            if pipeline_id:
                base_where.append(TestRun.pipeline_id == pipeline_id)
            if status:
                base_where.append(TestRun.status == status)

            count_stmt = select(func.count()).select_from(TestRun).where(*base_where)
            total = (await session.execute(count_stmt)).scalar() or 0

            stmt = (
                select(TestRun)
                .where(*base_where)
                .order_by(TestRun.created_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
            result = await session.execute(stmt)
            return list(result.scalars().all()), total

    async def get_by_id(self, id: str, tenant_id: Optional[str] = None) -> Optional[TestRun]:
        """根据 ID 查询单个运行"""
        async with self.db_session_factory() as session:
            stmt = select(TestRun).where(TestRun.id == id)
            if tenant_id is not None:
                stmt = stmt.where(TestRun.tenant_id == tenant_id)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def create(self, obj_data: Dict[str, Any]) -> TestRun:
        """创建测试运行"""
        return await super().create(obj_data)

    async def update(self, id: str, obj_data: Dict[str, Any], tenant_id: Optional[str] = None) -> TestRun:
        """更新测试运行"""
        return await super().update(id, obj_data, tenant_id)

    async def delete(self, id: Any, tenant_id: Optional[str] = None) -> bool:
        """删除测试运行"""
        return await super().delete(id, tenant_id)

    async def batch_delete(self, ids: List[str], tenant_id: Optional[str] = None) -> int:
        """批量删除测试运行

        Returns:
            实际删除的行数
        """
        async with self.db_session_factory() as session:
            stmt = delete(TestRun).where(TestRun.id.in_(ids))
            if tenant_id is not None:
                stmt = stmt.where(TestRun.tenant_id == tenant_id)
            result = await session.execute(stmt)
            await session.commit()
            return result.rowcount


class TestRunResultRepository(BaseRepository[TestRunResult]):
    """测试运行结果数据访问层"""

    def __init__(self, db_session_factory: async_sessionmaker):
        super().__init__(TestRunResult, db_session_factory)

    async def create_result(self, obj_data: Dict[str, Any]) -> TestRunResult:
        """创建运行结果"""
        return await super().create(obj_data)

    async def list_results(self, run_id: str) -> list[TestRunResult]:
        """查询某次运行的所有结果"""
        async with self.db_session_factory() as session:
            stmt = (
                select(TestRunResult)
                .where(TestRunResult.run_id == run_id)
                .order_by(TestRunResult.id)
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def get_result(self, run_id: str, case_id: str) -> Optional[TestRunResult]:
        """查询某次运行中指定用例的结果"""
        async with self.db_session_factory() as session:
            stmt = select(TestRunResult).where(
                TestRunResult.run_id == run_id,
                TestRunResult.test_case_id == case_id,
            )
            result = await session.execute(stmt)
            return result.scalar_one_or_none()
