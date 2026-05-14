"""文档 Repository"""
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from src.models.kb_document import KbDocument
from src.repository.base import BaseRepository


class DocumentRepository(BaseRepository[KbDocument]):
    """文档数据访问层"""

    def __init__(self, db_session_factory: async_sessionmaker):
        super().__init__(KbDocument, db_session_factory)

    async def get_by_md5(self, kb_id: str, tenant_id: str, md5_hash: str) -> Optional[KbDocument]:
        """根据 MD5 查找重复文档"""
        async with self.db_session_factory() as session:
            stmt = select(KbDocument).where(
                KbDocument.kb_id == kb_id,
                KbDocument.tenant_id == tenant_id,
                KbDocument.md5_hash == md5_hash,
            )
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def list_by_kb(
        self,
        kb_id: str,
        tenant_id: str,
        parse_status: Optional[str] = None,
        file_type: Optional[str] = None,
        keyword: Optional[str] = None,
        skip: int = 0,
        limit: int = 20,
    ) -> list[KbDocument]:
        """列出知识库下的文档"""
        async with self.db_session_factory() as session:
            stmt = select(KbDocument).where(
                KbDocument.kb_id == kb_id,
                KbDocument.tenant_id == tenant_id,
            )

            if parse_status:
                stmt = stmt.where(KbDocument.parse_status == parse_status)
            if file_type:
                stmt = stmt.where(KbDocument.file_type == file_type)
            if keyword:
                stmt = stmt.where(KbDocument.filename.ilike(f"%{keyword}%"))

            stmt = stmt.order_by(KbDocument.uploaded_at.desc())
            stmt = stmt.offset(skip).limit(limit)

            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def count_by_kb(
        self,
        kb_id: str,
        tenant_id: str,
        parse_status: Optional[str] = None,
    ) -> int:
        """统计知识库下的文档数"""
        from sqlalchemy import func

        async with self.db_session_factory() as session:
            stmt = select(func.count()).select_from(KbDocument).where(
                KbDocument.kb_id == kb_id,
                KbDocument.tenant_id == tenant_id,
            )
            if parse_status:
                stmt = stmt.where(KbDocument.parse_status == parse_status)
            result = await session.execute(stmt)
            return result.scalar() or 0

    async def update_parse_status(
        self, doc_id: str, tenant_id: str, status: str, error_message: Optional[str] = None
    ) -> None:
        """更新文档解析状态"""
        async with self.db_session_factory() as session:
            stmt = select(KbDocument).where(
                KbDocument.id == doc_id,
                KbDocument.tenant_id == tenant_id,
            )
            result = await session.execute(stmt)
            doc = result.scalar_one_or_none()
            if doc:
                doc.parse_status = status
                if error_message:
                    doc.error_message = error_message
                await session.commit()
