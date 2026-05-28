"""知识问答历史记录 Repository"""

from sqlalchemy import desc, func, select
from src.core.database import async_session_factory
from src.models.knowledge_qa_history import KnowledgeQAHistory


class KnowledgeQAHistoryRepository:
    """知识问答历史记录 Repository"""

    def __init__(self):
        self._session_factory = async_session_factory

    async def save(self, history: KnowledgeQAHistory) -> None:
        """保存或更新历史记录"""
        async with self._session_factory() as session:
            session.add(history)
            await session.commit()

    async def list_by_time(
        self, skip: int = 0, limit: int = 20
    ) -> list[KnowledgeQAHistory]:
        """按时间倒序获取历史列表"""
        async with self._session_factory() as session:
            result = await session.execute(
                select(KnowledgeQAHistory)
                .order_by(desc(KnowledgeQAHistory.created_at))
                .offset(skip)
                .limit(limit)
            )
            return list(result.scalars().all())

    async def count(self) -> int:
        """获取总记录数"""
        async with self._session_factory() as session:
            result = await session.execute(
                select(func.count()).select_from(KnowledgeQAHistory)
            )
            return result.scalar_one()

    async def get_by_task_id(self, task_id: str) -> KnowledgeQAHistory | None:
        """根据 task_id 获取历史记录"""
        async with self._session_factory() as session:
            result = await session.execute(
                select(KnowledgeQAHistory).where(
                    KnowledgeQAHistory.task_id == task_id
                )
            )
            return result.scalar_one_or_none()

    async def delete_by_task_id(self, task_id: str) -> bool:
        """根据 task_id 删除历史记录，返回是否成功"""
        from sqlalchemy import delete
        async with self._session_factory() as session:
            result = await session.execute(
                delete(KnowledgeQAHistory).where(
                    KnowledgeQAHistory.task_id == task_id
                )
            )
            await session.commit()
            return result.rowcount > 0

    async def delete_oldest(self, keep_count: int = 200) -> int:
        """删除超过 keep_count 条的最旧记录，返回删除条数"""
        from sqlalchemy import delete
        async with self._session_factory() as session:
            # 先获取需要保留的最小 created_at
            result = await session.execute(
                select(KnowledgeQAHistory.created_at)
                .order_by(desc(KnowledgeQAHistory.created_at))
                .offset(keep_count - 1)
                .limit(1)
            )
            oldest_kept = result.scalar_one_or_none()
            if oldest_kept is None:
                return 0

            result = await session.execute(
                delete(KnowledgeQAHistory).where(
                    KnowledgeQAHistory.created_at < oldest_kept
                )
            )
            await session.commit()
            return result.rowcount
