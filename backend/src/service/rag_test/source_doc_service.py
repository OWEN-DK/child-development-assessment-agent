import hashlib
import os
import shutil
import uuid
from typing import List, Optional

from sqlalchemy import select

from src.config import settings
from src.core.database import db_session_factory
from src.models.test_case import SourceDocument
from src.schemas import DocumentStatus
from src.utils.logger import logger

SOURCE_DOCUMENTS_DIR = f"{settings.rag_storage_dir}/source_documents"
os.makedirs(SOURCE_DOCUMENTS_DIR, exist_ok=True)


class SourceDocService:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SourceDocService, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self.db_session_factory = db_session_factory
        self._initialized = True

    def _compute_file_hash(self, file_path: str) -> str:
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        return sha256.hexdigest()

    async def upload_source_document(
        self, file_path: str, title: str, file_type: str
    ) -> SourceDocument:
        file_hash = self._compute_file_hash(file_path)

        async def _check_existing():
            async with self.db_session_factory() as session:
                stmt = select(SourceDocument).where(
                    SourceDocument.file_hash == file_hash
                )
                result = await session.execute(stmt)
                return result.scalar_one_or_none()

        existing_doc = await _check_existing()
        if existing_doc:
            logger.info(
                f"文档已存在，直接复用: {existing_doc.id} - {existing_doc.title}"
            )
            return existing_doc

        dest_path = os.path.join(
            SOURCE_DOCUMENTS_DIR, f"{file_hash}_{os.path.basename(file_path)}"
        )
        shutil.copy2(file_path, dest_path)

        doc = SourceDocument(
            id=str(uuid.uuid4()),
            title=title,
            file_type=file_type,
            file_path=dest_path,
            file_hash=file_hash,
            status=DocumentStatus.UPLOADED,
        )

        async def _save_doc():
            async with self.db_session_factory() as session:
                session.add(doc)
                await session.commit()
                await session.refresh(doc)
                return doc

        saved_doc = await _save_doc()

        logger.info(f"Source document uploaded: {saved_doc.id} - {title}")
        return saved_doc

    async def list_source_documents(self) -> List[SourceDocument]:
        async def _get_all():
            async with self.db_session_factory() as session:
                stmt = select(SourceDocument).order_by(SourceDocument.created_at.desc())
                result = await session.execute(stmt)
                return list(result.scalars().all())

        docs = await _get_all()
        return docs

    async def get_source_document(self, doc_id: str) -> Optional[SourceDocument]:
        async def _get_one():
            async with self.db_session_factory() as session:
                return await session.get(SourceDocument, doc_id)

        doc = await _get_one()
        return doc

    async def delete_source_document(self, doc_id: str) -> bool:
        async def _delete():
            async with self.db_session_factory() as session:
                doc = await session.get(SourceDocument, doc_id)
                if not doc:
                    return False

                if os.path.exists(doc.file_path):
                    os.remove(doc.file_path)

                await session.delete(doc)
                await session.commit()
                return True

        success = await _delete()

        if success:
            logger.info(f"Source document deleted: {doc_id}")
        return success


source_doc_service = SourceDocService()
