from typing import List, Optional

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from src.core.database import async_session_factory as _default_session_factory
from src.models.rag_eval.draft import TestCaseDraft
from src.repository.base import BaseRepository


class DraftRepository(BaseRepository[TestCaseDraft]):
    def __init__(self, db_session_factory: async_sessionmaker = _default_session_factory):
        super().__init__(TestCaseDraft, db_session_factory)

    async def get_by_status(
        self, status: str, skip: int = 0, limit: int = 100
    ) -> List[TestCaseDraft]:
        """根据状态查询草稿列表"""
        return await self.get_by_filter(
            status=status,
            skip=skip,
            limit=limit,
            order_by=desc(TestCaseDraft.created_at),
        )

    async def get_by_batch_id(
        self, batch_id: str, skip: int = 0, limit: int = 100
    ) -> List[TestCaseDraft]:
        """根据批次 ID 查询草稿列表"""
        return await self.get_by_filter(
            batch_id=batch_id,
            skip=skip,
            limit=limit,
            order_by=TestCaseDraft.draft_index,
        )

    async def get_by_source_document(
        self, source_document_id: str, skip: int = 0, limit: int = 100
    ) -> List[TestCaseDraft]:
        """根据来源文档 ID 查询草稿列表"""
        return await self.get_by_filter(
            source_document_id=source_document_id,
            skip=skip,
            limit=limit,
            order_by=desc(TestCaseDraft.created_at),
        )

    async def count_by_status(self, status: str) -> int:
        """统计指定状态的草稿数量"""
        return await self.count_by_filter(status=status)
