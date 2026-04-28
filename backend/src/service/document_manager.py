"""文档管理器（MySQL 存储）

职责：
- 通过 document_records 表跟踪文档导入进度/状态
- 文档索引成功后同步 upsert 到 source_documents 表
- 废弃原 JSON 文件存储方式
"""

from typing import List, Optional

from src.utils.logger import logger


class DocumentManager:
    """文档管理器（MySQL 存储，异步）

    保持单例语义：模块级 document_manager 实例在首次 import 时创建，
    所有消费方通过 from src.service.document_manager import document_manager 使用同一实例。
    """
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._doc_repo = None
            cls._instance._source_repo = None
        return cls._instance

    def _get_doc_repo(self):
        from src.repository.document_repository import DocumentRecordRepository
        from src.core.database import async_session_factory
        if self._doc_repo is None:
            self._doc_repo = DocumentRecordRepository(async_session_factory)
        return self._doc_repo

    def _get_source_repo(self):
        from src.repository.document_repository import SourceDocumentRepository
        from src.core.database import async_session_factory
        if self._source_repo is None:
            self._source_repo = SourceDocumentRepository(async_session_factory)
        return self._source_repo

    async def add_document(self, doc_dict: dict) -> None:
        """新增或更新文档记录（document_records），索引成功时同步 source_documents

        Args:
            doc_dict: 包含 file_hash, file_name, status 等字段的字典
        """
        from src.models.document import ImportStatus

        status_str = doc_dict.get("status", "pending")
        try:
            status_enum = ImportStatus(status_str)
        except ValueError:
            status_enum = ImportStatus.PENDING

        data = {
            "file_hash": doc_dict["file_hash"],
            "file_name": doc_dict["file_name"],
            "upload_date": doc_dict.get("upload_date"),
            "status": status_enum,
            "progress": int(doc_dict.get("progress", 0)),
            "total_pages": doc_dict.get("metadata", {}).get("total_pages") if isinstance(doc_dict.get("metadata"), dict) else None,
            "category": doc_dict.get("metadata", {}).get("category") if isinstance(doc_dict.get("metadata"), dict) else None,
            "ref_doc_ids": doc_dict.get("ref_doc_ids", []),
            "extra_metadata": doc_dict.get("metadata"),
        }
        if data["upload_date"] is None:
            from datetime import datetime
            data["upload_date"] = datetime.now()

        try:
            repo = self._get_doc_repo()
            await repo.upsert_by_file_hash(data)
        except Exception as e:
            logger.error(f"写入 document_records 失败: {e}")
            return

        if status_enum == ImportStatus.INDEXED:
            await self._sync_to_source_documents(doc_dict)

    async def _sync_to_source_documents(self, doc_dict: dict) -> None:
        """将已索引文档同步到 source_documents 表"""
        import os
        from src.models.document import DocumentStatus

        file_name = doc_dict["file_name"]
        file_hash = doc_dict["file_hash"]
        ext = os.path.splitext(file_name)[1].lstrip(".").lower() or "txt"
        metadata = doc_dict.get("metadata", {}) or {}
        if not isinstance(metadata, dict):
            metadata = {}

        source_data = {
            "file_hash": file_hash,
            "title": metadata.get("title", file_name),
            "file_type": ext,
            "file_path": file_name,
            "page_count": metadata.get("total_pages"),
            "chapter_count": metadata.get("chapter_count"),
            "status": DocumentStatus.READY,
        }
        try:
            source_repo = self._get_source_repo()
            await source_repo.upsert_by_file_hash(source_data)
            logger.info(f"已同步文档到 source_documents: {file_name}")
        except Exception as e:
            logger.error(f"同步 source_documents 失败: {e}")

    async def get_document(self, file_hash: str) -> Optional[dict]:
        """根据 file_hash 获取文档记录"""
        repo = self._get_doc_repo()
        orm = await repo.get_by_file_hash(file_hash)
        if not orm:
            return None
        return self._orm_to_dict(orm)

    async def get_document_by_name(self, file_name: str) -> Optional[dict]:
        """根据 file_name 获取文档记录"""
        repo = self._get_doc_repo()
        orm = await repo.get_by_file_name(file_name)
        if not orm:
            return None
        return self._orm_to_dict(orm)

    async def delete_document(self, file_hash: str) -> bool:
        """删除文档记录（同时删除 document_records 和 source_documents）"""
        repo = self._get_doc_repo()
        orm = await repo.get_by_file_hash(file_hash)
        if not orm:
            return False

        deleted = await repo.delete(orm.id)

        source_repo = self._get_source_repo()
        source = await source_repo.get_by_file_hash(file_hash)
        if source:
            await source_repo.delete(source.id)

        return deleted

    async def exists(self, file_hash: str) -> bool:
        """检查文档是否存在"""
        repo = self._get_doc_repo()
        orm = await repo.get_by_file_hash(file_hash)
        return orm is not None

    async def list_documents(self) -> List[dict]:
        """列出所有文档记录"""
        repo = self._get_doc_repo()
        orms = await repo.get_all(limit=10000)
        return [self._orm_to_dict(o) for o in orms]

    @staticmethod
    def _orm_to_dict(orm) -> dict:
        """ORM 对象转字典，保持与原 Pydantic DocumentRecord 兼容的格式"""
        metadata = {}
        if hasattr(orm, "extra_metadata") and orm.extra_metadata:
            if isinstance(orm.extra_metadata, dict):
                metadata = orm.extra_metadata

        return {
            "id": orm.id,
            "file_hash": orm.file_hash,
            "file_name": orm.file_name,
            "upload_date": orm.upload_date,
            "ref_doc_ids": orm.ref_doc_ids or [],
            "metadata": metadata,
            "status": orm.status.value if hasattr(orm.status, "value") else str(orm.status),
            "progress": float(orm.progress or 0),
        }


document_manager = DocumentManager()
