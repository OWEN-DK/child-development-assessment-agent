import asyncio
import os
from datetime import datetime
from typing import Any, Callable, Dict, Optional

from src.config import settings
from src.schemas import DocumentMetadata, DocumentRecord
from src.schemas.task import TaskState, TaskStatus
from src.service.document_ingestion.chunking_indexing import (
    ChunkingAndIndexing, _safe_call_callback
)
from src.service.document_ingestion.document_parser import DocumentParser
from src.service.document_manager import document_manager
from src.utils.di import get_task_state_service
from src.utils.exceptions import TaskCancelledException
from src.utils.logger import logger

TASK_TYPE = "upload"


class BookIngestor:
    def __init__(self, index_manager):
        self.index_manager = index_manager
        self.parser = DocumentParser()
        self.chunking_indexing = ChunkingAndIndexing(index_manager)
        from src.core.pageindex_wrapper import PageIndexWrapper
        self.pageindex_wrapper = PageIndexWrapper()

    async def ingest_book_resumable(self, file_path: str, original_filename: str = None, progress_callback: Callable[[str, float, str], None] = None, task_id: str = None, force_restart: bool = False, max_concurrency: int = 4) -> str:
        import uuid
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
        file_name = original_filename if original_filename else os.path.basename(file_path)
        file_hash = self.parser.calculate_file_hash(file_path)
        if not force_restart:
            if document_manager.exists(file_hash):
                logger.warning(f"Document {file_path} already exists (hash: {file_hash}). Skipping ingestion.")
                return file_hash
        task_state_service = get_task_state_service()
        if task_id and not force_restart:
            existing_state = await task_state_service.get(task_id, TASK_TYPE)
            if existing_state and existing_state.status.value in ("pending", "running"):
                logger.info(f"Resuming import task: {task_id}, progress: {existing_state.progress}%")
                return await self._resume_import_task(task_id, existing_state, progress_callback, max_concurrency)
        if not task_id:
            task_id = str(uuid.uuid4())
            # 仅当 task_id 是内部生成时才创建新 Task（Controller 已创建的 task_id 不重复创建）
            logger.info(f"Starting new import task: {task_id}, file: {file_name}")
            
            initial_state = TaskState(
                task_id=task_id,
                task_type=TASK_TYPE,
                status=TaskStatus.RUNNING,
                progress=0.0,
                message="正在解析文件",
                stage="parsing",
                created_at=datetime.now().timestamp(),
                metadata={"file_path": file_path, "filename": file_name, "file_hash": file_hash, "processed_sections": [], "max_concurrency": max_concurrency}
            )
            await task_state_service.create(initial_state)
            try:
                await self._ingest_book_with_state(task_id, file_path, file_name, file_hash, initial_state, progress_callback)
                await task_state_service.update(
                    task_id=task_id, task_type=TASK_TYPE,
                    updates={"status": TaskStatus.COMPLETED, "progress": 100.0, "message": "导入完成"}
                )
                logger.info(f"Import task {task_id} completed successfully, file_hash={file_hash}")
                return file_hash
            except Exception as e:
                await task_state_service.update(
                    task_id=task_id, task_type=TASK_TYPE,
                    updates={"status": TaskStatus.FAILED, "error": str(e), "message": "导入失败"}
                )
                logger.error(f"Import task {task_id} failed: {e}")
                raise
        else:
            # task_id 由 Controller 传入，直接使用，不创建新 Task
            logger.info(f"Using existing task: {task_id}, file: {file_name}")
            try:
                await self._ingest_book_with_state(task_id, file_path, file_name, file_hash, progress_callback=progress_callback)
                await task_state_service.update(
                    task_id=task_id, task_type=TASK_TYPE,
                    updates={"status": TaskStatus.COMPLETED, "progress": 100.0, "message": "导入完成"}
                )
                logger.info(f"Import task {task_id} completed successfully, file_hash={file_hash}")
                return file_hash
            except Exception as e:
                await task_state_service.update(
                    task_id=task_id, task_type=TASK_TYPE,
                    updates={"status": TaskStatus.FAILED, "error": str(e), "message": "导入失败"}
                )
                logger.error(f"Import task {task_id} failed: {e}")
                raise

    async def _resume_import_task(self, task_id: str, task_state: TaskState, progress_callback: Callable[[str, float, str], None] = None, max_concurrency: int = 4) -> str:
        task_state_service = get_task_state_service()
        file_path = task_state.metadata.get("file_path")
        file_hash = task_state.metadata.get("file_hash")
        file_name = task_state.metadata.get("filename")
        logger.info(f"Resuming import task {task_id} from stage: {task_state.stage or 'parsing'}")
        
        try:
            if task_state.stage == "parsing" or not task_state.stage:
                return await self.ingest_book_resumable(file_path, file_name, progress_callback, task_id, force_restart=True, max_concurrency=max_concurrency)
            await self._ingest_book_with_state(task_id, file_path, file_name, file_hash, task_state, progress_callback)
            await task_state_service.update(
                task_id=task_id, task_type=TASK_TYPE,
                updates={"status": TaskStatus.COMPLETED, "progress": 100.0, "message": "导入完成"}
            )
            logger.info(f"Resumed import task {task_id} completed successfully")
            return file_hash
        except Exception as e:
            await task_state_service.update(
                task_id=task_id, task_type=TASK_TYPE,
                updates={"status": TaskStatus.FAILED, "error": str(e), "message": "导入失败"}
            )
            logger.error(f"Resumed import task {task_id} failed: {e}")
            raise

    async def _ingest_book_with_state(self, task_id: str, file_path: str, file_name: str, file_hash: str, task_state: Optional[TaskState] = None, progress_callback: Callable[[str, float, str], None] = None):
        task_state_service = get_task_state_service()
        try:
            actual_total_pages = self.parser.get_actual_total_pages(file_path)
            if progress_callback:
                await _safe_call_callback(progress_callback, "parsing", 10.0, "正在解析文件")
            await task_state_service.update(
                task_id=task_id, task_type=TASK_TYPE,
                updates={"progress": 10.0, "stage": "parsing", "message": "正在解析文件"}
            )

            loop = asyncio.get_running_loop()
            def page_progress_callback(current_page: int, total_pages: int):
                if progress_callback and actual_total_pages:
                    parse_progress = 10.0 + (current_page / actual_total_pages) * 20.0
                    res = progress_callback("parsing", parse_progress, f"正在解析文件，第 {current_page}/{actual_total_pages} 页")
                    if asyncio.iscoroutine(res):
                        asyncio.run_coroutine_threadsafe(res, loop)

            documents, parser_cls = await asyncio.to_thread(
                self.parser.parse_document, file_path, page_progress_callback
            )
            # 使用线程池执行同步的 VL 解析检查，避免阻塞事件循环
            documents = await asyncio.to_thread(
                self.parser.check_vl_parsing, file_path, documents, parser_cls
            )
            if not documents:
                raise ValueError("无法从文件中提取文本。该文件可能是扫描版PDF或空文件，且无法使用VL模型识别。")
            logger.info(f"Parsed {len(documents)} document chunks/pages.")

            # 使用线程池执行同步的章节计算和文档清理，避免阻塞事件循环
            chapter_count = await asyncio.to_thread(
                self.parser.calculate_chapter_count, file_path, documents
            )
            documents = await asyncio.to_thread(
                self.parser.clean_documents, documents, file_name
            )
            if not documents:
                logger.error(f"No valid content found in {file_name} after cleaning")
                raise ValueError(f"文件 {file_name} 中未找到有效内容，请检查文件内容是否正常")

            pending_doc, doc_count = await self.chunking_indexing.process_chunks_and_index(
                documents, file_path, file_name, file_hash, task_id, progress_callback
            )

            if progress_callback:
                await _safe_call_callback(progress_callback, "processing", 98.0, "正在完成最终操作")

            doc_record = DocumentRecord(file_hash=file_hash, file_name=file_name, ref_doc_ids=[file_hash], metadata=DocumentMetadata(title=file_name, total_pages=actual_total_pages if actual_total_pages is not None else doc_count, chapter_count=chapter_count), status="indexed", progress=100.0)
            # 使用线程池执行同步的文件写入操作，避免阻塞事件循环
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, document_manager.add_document, doc_record)
            if settings.pageindex_enabled:
                asyncio.create_task(self.pageindex_wrapper.index_document(file_path, file_hash))
            logger.info(f"Successfully ingested {file_path}")
            if progress_callback:
                await _safe_call_callback(progress_callback, "completed", 100.0, "文档导入完成")
            await task_state_service.update(
                task_id=task_id, task_type=TASK_TYPE,
                updates={"progress": 100.0, "message": "文档导入完成"}
            )
        except TaskCancelledException:
            logger.info(f"Task cancelled for {file_name}. Cleaning up...")
            if document_manager.exists(file_hash):
                document_manager.delete_document(file_hash)
            raise
        except Exception as e:
            logger.error(f"Failed to ingest book: {e}", exc_info=True)
            try:
                failed_doc = DocumentRecord(file_hash=file_hash, file_name=file_name, ref_doc_ids=[file_hash], metadata=DocumentMetadata(title=file_name, total_pages=0), status="failed", progress=0.0)
                # 使用线程池执行同步的文件写入操作，避免阻塞事件循环
                loop = asyncio.get_running_loop()
                await loop.run_in_executor(None, document_manager.add_document, failed_doc)
            except:
                pass
            raise

    async def ingest_book(self, file_path: str, original_filename: str = None, progress_callback: Callable[[str, float, str], None] = None, task_id: str = None):
        return await self.ingest_book_resumable(file_path, original_filename, progress_callback, task_id=task_id, force_restart=True)
