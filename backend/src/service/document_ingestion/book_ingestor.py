import asyncio
import os
from datetime import datetime
from typing import Any, Callable, Dict, Optional

from src.config import settings
from src.schemas import DocumentMetadata, DocumentRecord
from src.service.document_ingestion.chunking_indexing import \
    ChunkingAndIndexing
from src.service.document_ingestion.document_parser import DocumentParser
from src.service.document_ingestion.task_state_manager import TaskStatus
from src.service.document_manager import document_manager
from src.utils.exceptions import TaskCancelledException
from src.utils.logger import logger


class BookIngestor:
    def __init__(self, index_manager, task_manager):
        self.index_manager = index_manager
        self.task_manager = task_manager
        self.parser = DocumentParser()
        self.chunking_indexing = ChunkingAndIndexing(index_manager, task_manager)
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
            existing_task = self.task_manager.load_task_by_file_hash(file_hash)
            if existing_task:
                logger.info(f"File already imported, returning existing doc_id: {file_hash}")
                return file_hash
        task_state = None
        if task_id and not force_restart:
            task_state = self.task_manager.load_task_state(task_id)
            if task_state:
                logger.info(f"Resuming import task: {task_id}, progress: {task_state.get('progress', 0)}%")
                return await self._resume_import_task(task_state, progress_callback, max_concurrency)
        if not task_id:
            task_id = str(uuid.uuid4())
        logger.info(f"Starting new import task: {task_id}, file: {file_name}")
        task_state = {"task_id": task_id, "file_path": file_path, "file_name": file_name, "file_hash": file_hash, "progress": 0, "status": TaskStatus.RUNNING, "created_at": datetime.now().isoformat(), "current_stage": "parsing", "processed_sections": [], "max_concurrency": max_concurrency}
        self.task_manager.save_task_state(task_id, task_state)
        try:
            await self._ingest_book_with_state(task_state, progress_callback)
            task_state["status"] = TaskStatus.COMPLETED
            task_state["completed_at"] = datetime.now().isoformat()
            self.task_manager.save_task_state(task_id, task_state)
            logger.info(f"Import task {task_id} completed successfully, file_hash={file_hash}")
            return file_hash
        except Exception as e:
            task_state["status"] = TaskStatus.FAILED
            task_state["error"] = str(e)
            task_state["failed_at"] = datetime.now().isoformat()
            self.task_manager.save_task_state(task_id, task_state)
            logger.error(f"Import task {task_id} failed: {e}")
            raise

    async def _resume_import_task(self, task_state: Dict[str, Any], progress_callback: Callable[[str, float, str], None] = None, max_concurrency: int = 4) -> str:
        task_id = task_state["task_id"]
        file_path = task_state["file_path"]
        file_hash = task_state["file_hash"]
        logger.info(f"Resuming import task {task_id} from stage: {task_state.get('current_stage', 'parsing')}")
        try:
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"File not found: {file_path}")
            current_file_hash = self.parser.calculate_file_hash(file_path)
            if current_file_hash != file_hash:
                logger.warning("File content changed, restarting import from beginning")
                return await self.ingest_book_resumable(file_path, task_state["file_name"], progress_callback, task_id, force_restart=True, max_concurrency=max_concurrency)
            await self._ingest_book_with_state(task_state, progress_callback)
            task_state["status"] = TaskStatus.COMPLETED
            task_state["completed_at"] = datetime.now().isoformat()
            self.task_manager.save_task_state(task_id, task_state)
            logger.info(f"Resumed import task {task_id} completed successfully")
            return file_hash
        except Exception as e:
            task_state["status"] = TaskStatus.FAILED
            task_state["error"] = str(e)
            task_state["failed_at"] = datetime.now().isoformat()
            self.task_manager.save_task_state(task_id, task_state)
            logger.error(f"Resumed import task {task_id} failed: {e}")
            raise

    async def _ingest_book_with_state(self, task_state: Dict[str, Any], progress_callback: Callable[[str, float, str], None] = None):
        file_path = task_state["file_path"]
        file_name = task_state["file_name"]
        file_hash = task_state["file_hash"]
        task_id = task_state["task_id"]
        try:
            actual_total_pages = self.parser.get_actual_total_pages(file_path)
            task_state["current_stage"] = "parsing"
            if progress_callback:
                progress_callback("parsing", 10.0, "正在解析文件")
                task_state["progress"] = 10.0
                self.task_manager.save_task_state(task_id, task_state)

            def page_progress_callback(current_page: int, total_pages: int):
                if progress_callback and actual_total_pages:
                    parse_progress = 10.0 + (current_page / actual_total_pages) * 20.0
                    progress_callback("parsing", parse_progress, f"正在解析文件，第 {current_page}/{actual_total_pages} 页")
                    task_state["progress"] = parse_progress
                    self.task_manager.save_task_state(task_id, task_state)

            documents, parser_cls = self.parser.parse_document(file_path, progress_callback=page_progress_callback)
            documents = self.parser.check_vl_parsing(file_path, documents, parser_cls)
            if not documents:
                raise ValueError("无法从文件中提取文本。该文件可能是扫描版PDF或空文件，且无法使用VL模型识别。")
            logger.info(f"Parsed {len(documents)} document chunks/pages.")

            chapter_count = self.parser.calculate_chapter_count(file_path, documents)
            documents = self.parser.clean_documents(documents, file_name)
            if not documents:
                logger.error(f"No valid content found in {file_name} after cleaning")
                raise ValueError(f"文件 {file_name} 中未找到有效内容，请检查文件内容是否正常")

            pending_doc, doc_count = await self.chunking_indexing.process_chunks_and_index(
                documents, file_path, file_name, file_hash, task_id, task_state, progress_callback
            )

            doc_record = DocumentRecord(file_hash=file_hash, file_name=file_name, ref_doc_ids=[file_hash], metadata=DocumentMetadata(title=file_name, total_pages=actual_total_pages if actual_total_pages is not None else doc_count, chapter_count=chapter_count), status="indexed", progress=100.0)
            document_manager.add_document(doc_record)
            if settings.pageindex_enabled:
                asyncio.create_task(self.pageindex_wrapper.index_document(file_path, file_hash))
            logger.info(f"Successfully ingested {file_path}")
            if progress_callback:
                progress_callback("completed", 100.0, "文档导入完成")
            task_state["progress"] = 100.0
            self.task_manager.save_task_state(task_id, task_state)
        except TaskCancelledException:
            logger.info(f"Task cancelled for {file_name}. Cleaning up...")
            if document_manager.exists(file_hash):
                document_manager.delete_document(file_hash)
            raise
        except Exception as e:
            logger.error(f"Failed to ingest book: {e}", exc_info=True)
            try:
                failed_doc = DocumentRecord(file_hash=file_hash, file_name=file_name, ref_doc_ids=[file_hash], metadata=DocumentMetadata(title=file_name, total_pages=0), status="failed", progress=0.0)
                document_manager.add_document(failed_doc)
            except:
                pass
            raise

    async def ingest_book(self, file_path: str, original_filename: str = None, progress_callback: Callable[[str, float, str], None] = None):
        return await self.ingest_book_resumable(file_path, original_filename, progress_callback, force_restart=True)
