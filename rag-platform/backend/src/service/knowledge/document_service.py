"""文档服务

文档上传、解析、分块、向量化流水线。
"""
import asyncio
import hashlib
import os
import uuid
from pathlib import Path
from typing import Optional

from sqlalchemy.ext.asyncio import async_sessionmaker

from src.core.knowledge_base.chunking.engine import ChunkingEngine
from src.core.knowledge_base.embedding.engine import EmbeddingEngine
from src.core.knowledge_base.parser import get_parser
from src.core.knowledge_base.vector_store.factory import VectorStoreAdapterFactory
from src.models.kb_document import KbDocument
from src.repository.knowledge.chunk_repo import ChunkRepository
from src.repository.knowledge.document_repo import DocumentRepository
from src.repository.knowledge.kb_repo import KnowledgeBaseRepository
from src.schemas.knowledge.document import (
    BatchUploadResult,
    DocumentDetail,
    DocumentList,
    DocumentSummary,
    ParseStatus,
)
from src.service.knowledge.constants import (
    FILE_TYPE_MAP,
    MAX_BATCH_FILES,
    MAX_FILE_SIZE_BYTES,
    SUPPORTED_FILE_TYPES,
)
from src.utils.logger import logger


class DocumentService:
    """文档服务"""

    def __init__(self, db_session_factory: async_sessionmaker):
        self.db_session_factory = db_session_factory
        self.doc_repo = DocumentRepository(db_session_factory)
        self.chunk_repo = ChunkRepository(db_session_factory)
        self.kb_repo = KnowledgeBaseRepository(db_session_factory)
        self.chunking_engine = ChunkingEngine()

    async def upload(
        self,
        kb_id: str,
        tenant_id: str,
        user_id: str,
        files: list[tuple[str, bytes]],  # [(filename, content), ...]
    ) -> BatchUploadResult:
        """批量上传文档

        Args:
            kb_id: 知识库 ID
            tenant_id: 租户 ID
            user_id: 用户 ID
            files: 文件列表 [(filename, content), ...]

        Returns:
            BatchUploadResult
        """
        result = BatchUploadResult()

        for filename, content in files:
            try:
                # 检查文件大小
                if len(content) > MAX_FILE_SIZE_BYTES:
                    result.errors.append({
                        "filename": filename,
                        "error": f"文件大小超过限制（{MAX_FILE_SIZE_BYTES // 1024 // 1024}MB）",
                    })
                    result.total_errors += 1
                    continue

                # 检查文件类型
                ext = os.path.splitext(filename)[1].lower()
                file_type = FILE_TYPE_MAP.get(ext)
                if not file_type:
                    result.errors.append({
                        "filename": filename,
                        "error": f"不支持的文件类型: {ext}",
                    })
                    result.total_errors += 1
                    continue

                # 计算 MD5
                md5_hash = hashlib.md5(content).hexdigest()

                # 检查重复
                existing = await self.doc_repo.get_by_md5(kb_id, tenant_id, md5_hash)
                if existing:
                    result.duplicates.append(self._to_summary(existing))
                    result.total_duplicates += 1
                    continue

                # 保存文件
                doc_id = self._generate_id()
                storage_dir = os.getenv("RAG_STORAGE_DIR", "./app_data/storage")
                file_dir = Path(storage_dir) / "documents" / tenant_id / kb_id
                file_dir.mkdir(parents=True, exist_ok=True)
                file_path = file_dir / f"{doc_id}{ext}"
                file_path.write_bytes(content)

                # 创建文档记录
                doc_data = {
                    "id": doc_id,
                    "kb_id": kb_id,
                    "tenant_id": tenant_id,
                    "filename": filename,
                    "file_type": file_type,
                    "file_size": len(content),
                    "md5_hash": md5_hash,
                    "parse_status": "pending",
                    "owner_id": user_id,
                }
                doc = await self.doc_repo.create(doc_data)
                result.created.append(self._to_summary(doc))
                result.total_uploaded += 1

                # 异步触发解析
                asyncio.create_task(self._parse_async(doc_id, str(file_path), file_type, kb_id, tenant_id))

            except Exception as e:
                logger.error(f"文档上传失败: {filename}, {e}")
                result.errors.append({"filename": filename, "error": str(e)})
                result.total_errors += 1

        return result

    async def _parse_async(
        self, doc_id: str, file_path: str, file_type: str,
        kb_id: str, tenant_id: str
    ) -> None:
        """异步解析流水线：解析 → 分块 → 向量化 → 索引更新"""
        try:
            # 更新状态为解析中
            await self.doc_repo.update_parse_status(doc_id, tenant_id, "parsing")

            # 1. 解析文档
            parser = get_parser(f".{file_type}")
            documents = parser.parse(file_path)

            # 合并所有文本
            full_text = "\n\n".join([d["text"] for d in documents])
            if not full_text.strip():
                await self.doc_repo.update_parse_status(doc_id, tenant_id, "error", "解析结果为空")
                return

            # 更新文档文本内容
            await self.doc_repo.update(doc_id, {
                "text_content": full_text[:100000],  # 限制存储大小
                "page_count": len(documents),
                "metadata": documents[0]["metadata"] if documents else {},
            }, tenant_id)

            # 2. 分块
            kb = await self.kb_repo.get_by_id(kb_id, tenant_id)
            chunk_config = kb.chunk_strategy if kb and kb.chunk_strategy else {"type": "fixed_size", "chunk_size": 512, "overlap": 50}
            chunks = self.chunking_engine.chunk(full_text, chunk_config)

            # 3. 保存分块到数据库
            chunk_records = []
            for i, chunk in enumerate(chunks):
                chunk_records.append({
                    "id": self._generate_id(),
                    "kb_id": kb_id,
                    "doc_id": doc_id,
                    "tenant_id": tenant_id,
                    "chunk_index": i,
                    "content": chunk.content,
                    "token_count": chunk.token_count,
                    "metadata": chunk.metadata,
                })

            if chunk_records:
                await self.chunk_repo.batch_insert(chunk_records)

            # 4. 更新文档状态
            await self.doc_repo.update(doc_id, {
                "parse_status": "parsed",
                "chunk_count": len(chunks),
            }, tenant_id)

            # 5. 更新知识库统计
            await self.kb_repo.increment_counts(kb_id, tenant_id, doc_delta=1, chunk_delta=len(chunks))

            logger.info(f"文档解析完成: {doc_id}, {len(chunks)} 个分块")

        except Exception as e:
            logger.error(f"文档解析失败: {doc_id}, {e}")
            await self.doc_repo.update_parse_status(doc_id, tenant_id, "error", str(e))

    async def list_documents(
        self,
        kb_id: str,
        tenant_id: str,
        parse_status: Optional[str] = None,
        file_type: Optional[str] = None,
        keyword: Optional[str] = None,
        skip: int = 0,
        limit: int = 20,
    ) -> DocumentList:
        """列出文档"""
        items = await self.doc_repo.list_by_kb(
            kb_id=kb_id,
            tenant_id=tenant_id,
            parse_status=parse_status,
            file_type=file_type,
            keyword=keyword,
            skip=skip,
            limit=limit,
        )
        total = await self.doc_repo.count_by_kb(kb_id, tenant_id, parse_status)
        return DocumentList(
            items=[self._to_summary(doc) for doc in items],
            total=total,
        )

    async def get_detail(self, doc_id: str, kb_id: str, tenant_id: str) -> DocumentDetail:
        """获取文档详情（含分块预览）"""
        doc = await self.doc_repo.get_by_id(doc_id, tenant_id)
        if not doc or doc.kb_id != kb_id:
            raise ValueError(f"文档不存在: {doc_id}")

        # 获取前 10 个分块
        chunks = await self.chunk_repo.get_by_doc_id(doc_id, tenant_id, limit=10)

        return DocumentDetail(
            id=doc.id,
            kb_id=doc.kb_id,
            tenant_id=doc.tenant_id,
            filename=doc.filename,
            file_type=doc.file_type,
            file_size=doc.file_size,
            page_count=doc.page_count,
            md5_hash=doc.md5_hash,
            parse_status=doc.parse_status,
            error_message=doc.error_message,
            text_content=doc.text_content[:5000] if doc.text_content else None,
            metadata=doc.metadata,
            access_level=doc.access_level,
            doc_acl=doc.doc_acl,
            owner_id=doc.owner_id,
            chunk_count=doc.chunk_count,
            uploaded_at=doc.uploaded_at,
            chunk_preview=[
                {
                    "chunk_index": c.chunk_index,
                    "content": c.content[:500],
                    "char_count": len(c.content),
                    "token_estimate": c.token_count or int(len(c.content) * 1.3),
                }
                for c in chunks
            ],
        )

    async def delete(self, doc_id: str, kb_id: str, tenant_id: str) -> None:
        """删除文档（级联删除分块）"""
        doc = await self.doc_repo.get_by_id(doc_id, tenant_id)
        if not doc or doc.kb_id != kb_id:
            raise ValueError(f"文档不存在: {doc_id}")

        # 删除分块
        chunk_count = await self.chunk_repo.delete_by_doc_id(doc_id, tenant_id)

        # 删除文档记录
        await self.doc_repo.delete(doc_id, tenant_id)

        # 更新知识库统计
        await self.kb_repo.increment_counts(kb_id, tenant_id, doc_delta=-1, chunk_delta=-chunk_count)

        # 删除文件
        try:
            storage_dir = os.getenv("RAG_STORAGE_DIR", "./app_data/storage")
            file_dir = Path(storage_dir) / "documents" / tenant_id / kb_id
            for f in file_dir.glob(f"{doc_id}.*"):
                f.unlink()
        except Exception as e:
            logger.warning(f"删除文档文件失败: {e}")

        logger.info(f"文档删除完成: {doc_id}")

    def _generate_id(self) -> str:
        return str(uuid.uuid4()).replace("-", "")[:24]

    def _to_summary(self, doc: KbDocument) -> DocumentSummary:
        return DocumentSummary(
            id=doc.id,
            kb_id=doc.kb_id,
            filename=doc.filename,
            file_type=doc.file_type,
            file_size=doc.file_size,
            page_count=doc.page_count,
            md5_hash=doc.md5_hash,
            parse_status=doc.parse_status,
            error_message=doc.error_message,
            access_level=doc.access_level,
            owner_id=doc.owner_id,
            chunk_count=doc.chunk_count,
            uploaded_at=doc.uploaded_at,
        )
