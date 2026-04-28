from typing import List, Optional

from sqlalchemy.ext.asyncio import async_sessionmaker

from src.models.document import DocumentRecord, DocumentStatus, ImportStatus, SourceDocument
from src.repository.base import BaseRepository
from src.utils.id_generator import generate_id


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

    async def upsert_by_file_hash(self, data: dict) -> SourceDocument:
        """根据 file_hash 执行 upsert"""
        existing = await self.get_by_file_hash(data["file_hash"])
        if existing:
            return await self.update(existing.id, data)
        if "id" not in data:
            data["id"] = generate_id()
        return await self.create(data)

    async def get_indexed(self, skip: int = 0, limit: int = 100) -> List[SourceDocument]:
        """查询所有就绪的源文档"""
        return await self.get_by_filter(skip=skip, limit=limit, status=DocumentStatus.READY)

    async def count_indexed(self) -> int:
        """统计就绪源文档数量"""
        return await self.count_by_filter(status=DocumentStatus.READY)


class DocumentRecordRepository(BaseRepository[DocumentRecord]):
    def __init__(self, db_session_factory: async_sessionmaker):
        super().__init__(DocumentRecord, db_session_factory)

    async def get_by_file_hash(self, file_hash: str) -> Optional[DocumentRecord]:
        """根据文件哈希查询文档记录"""
        return await self.get_one_by_filter(file_hash=file_hash)

    async def get_by_file_name(self, file_name: str) -> Optional[DocumentRecord]:
        """根据文件名查询文档记录"""
        return await self.get_one_by_filter(file_name=file_name)

    async def get_indexed(self, skip: int = 0, limit: int = 100) -> List[DocumentRecord]:
        """查询所有已索引的文档记录"""
        return await self.get_by_filter(skip=skip, limit=limit, status=ImportStatus.INDEXED)

    async def count_indexed(self) -> int:
        """统计已索引文档数量"""
        return await self.count_by_filter(status=ImportStatus.INDEXED)

    async def upsert_by_file_hash(self, data: dict) -> DocumentRecord:
        """根据 file_hash 执行 upsert（存在则更新，不存在则创建）"""
        existing = await self.get_by_file_hash(data["file_hash"])
        if existing:
            return await self.update(existing.id, data)
        if "id" not in data:
            data["id"] = generate_id()
        return await self.create(data)
