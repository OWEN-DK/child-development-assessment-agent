"""重建任务 Repository"""
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from src.models.kb_rebuild_task import KbRebuildTask
from src.repository.base import BaseRepository


class RebuildTaskRepository(BaseRepository[KbRebuildTask]):
    """重建任务数据访问层"""

    def __init__(self, db_session_factory: async_sessionmaker):
        super().__init__(KbRebuildTask, db_session_factory)

    async def get_latest_running(self, kb_id: str, tenant_id: str) -> Optional[KbRebuildTask]:
        """获取知识库最新的运行中重建任务"""
        async with self.db_session_factory() as session:
            stmt = select(KbRebuildTask).where(
                KbRebuildTask.kb_id == kb_id,
                KbRebuildTask.tenant_id == tenant_id,
                KbRebuildTask.status == "running",
            ).order_by(KbRebuildTask.started_at.desc()).limit(1)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def get_recent(
        self, kb_id: str, tenant_id: str, limit: int = 10
    ) -> list[KbRebuildTask]:
        """获取知识库最近的重建任务"""
        async with self.db_session_factory() as session:
            stmt = select(KbRebuildTask).where(
                KbRebuildTask.kb_id == kb_id,
                KbRebuildTask.tenant_id == tenant_id,
            ).order_by(KbRebuildTask.started_at.desc()).limit(limit)
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def update_progress(
        self, task_id: str, progress_pct: int, progress_message: str
    ) -> None:
        """更新重建任务进度"""
        async with self.db_session_factory() as session:
            stmt = select(KbRebuildTask).where(KbRebuildTask.id == task_id)
            result = await session.execute(stmt)
            task = result.scalar_one_or_none()
            if task:
                task.progress_pct = progress_pct
                task.progress_message = progress_message
                await session.commit()

    async def mark_completed(self, task_id: str) -> None:
        """标记重建任务完成"""
        from datetime import datetime

        async with self.db_session_factory() as session:
            stmt = select(KbRebuildTask).where(KbRebuildTask.id == task_id)
            result = await session.execute(stmt)
            task = result.scalar_one_or_none()
            if task:
                task.status = "completed"
                task.progress_pct = 100
                task.completed_at = datetime.utcnow()
                await session.commit()

    async def mark_failed(self, task_id: str, error_message: str) -> None:
        """标记重建任务失败"""
        from datetime import datetime

        async with self.db_session_factory() as session:
            stmt = select(KbRebuildTask).where(KbRebuildTask.id == task_id)
            result = await session.execute(stmt)
            task = result.scalar_one_or_none()
            if task:
                task.status = "failed"
                task.error_message = error_message
                task.completed_at = datetime.utcnow()
                await session.commit()
