from typing import List, Optional

from sqlalchemy.ext.asyncio import async_sessionmaker

from src.models.document import DocumentRecord, SourceDocument
from src.repository.base import BaseRepository


class SourceDocumentRepository(BaseRepository[SourceDocument]):
    def __init__(self, db_session_factory: async_sessionmaker):
        super().__init__(SourceDocument, db_session_factory)

    async def get_by_file_hash(self, file_hash: str) -> Optional[SourceDocument]:
        """根据文件哈希查询文档"""
        return await self.get_one_by_filter(file_hash=file_hash)

    async def get_by_status(
        self, status: str, skip: int = 0, limit: int = 50
    ) -> List[SourceDocument]:
        """根据状态查询文档"""
        return await self.get_by_filter(skip=skip, limit=limit, status=status)


class DocumentRecordRepository(BaseRepository[DocumentRecord]):
    def __init__(self, db_session_factory: async_sessionmaker):
        super().__init__(DocumentRecord, db_session_factory)

    async def get_by_file_hash(self, file_hash: str) -> Optional[DocumentRecord]:
        """根据文件哈希查询文档记录"""
        return await self.get_one_by_filter(file_hash=file_hash)
