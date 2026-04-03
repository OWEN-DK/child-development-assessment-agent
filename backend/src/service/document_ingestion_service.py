import os
import json
import hashlib
import re
import asyncio
from datetime import datetime, timedelta
from typing import Optional, Callable, List, Dict, Any
from llama_index.core.schema import Document
from src.config.settings import settings
from src.utils.logger import logger
from src.utils.exceptions import TaskCancelledException
from src.core.parsers import get_parser, PDFParser, PDFVLParser
from src.core.metadata_processor import MetadataProcessor
from src.model.document import DocumentRecord, DocumentMetadata
from src.service.document_manager import document_manager
from src.service.index_manager_service import IndexManagerService
from src.service.content_audit_service import content_audit_service


class TaskStatus:
    """任务状态枚举"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ImportTaskManager:
    """导入任务状态管理，支持断点续传"""
    
    def __init__(self, state_expire_days: int = 7):
        self.task_dir = os.path.join(settings.data_dir, "import_tasks")
        self.state_expire_days = state_expire_days
        os.makedirs(self.task_dir, exist_ok=True)
        # 初始化时清理过期任务
        self._cleanup_expired_tasks()
    
    def _cleanup_expired_tasks(self) -> None:
        """清理过期的任务状态文件"""
        now = datetime.now()
        expire_threshold = now - timedelta(days=self.state_expire_days)
        
        for filename in os.listdir(self.task_dir):
            if not filename.endswith(".json"):
                continue
            
            file_path = os.path.join(self.task_dir, filename)
            try:
                mtime = datetime.fromtimestamp(os.path.getmtime(file_path))
                if mtime < expire_threshold:
                    os.remove(file_path)
                    logger.info(f"Cleaned up expired import task state: {filename}")
            except Exception as e:
                logger.warning(f"Failed to cleanup task state {filename}: {e}")
    
    def save_task_state(self, task_id: str, state: Dict[str, Any]) -> None:
        """保存导入任务状态"""
        state_path = os.path.join(self.task_dir, f"{task_id}.json")
        # 添加更新时间戳
        state["updated_at"] = datetime.now().isoformat()
        with open(state_path, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    
    def load_task_state(self, task_id: str) -> Optional[Dict[str, Any]]:
        """加载导入任务状态"""
        state_path = os.path.join(self.task_dir, f"{task_id}.json")
        if os.path.exists(state_path):
            try:
                with open(state_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load task state {task_id}: {e}")
                return None
        return None
    
    def load_task_by_file_hash(self, file_hash: str) -> Optional[Dict[str, Any]]:
        """根据文件哈希查找已完成的导入任务"""
        for filename in os.listdir(self.task_dir):
            if not filename.endswith(".json"):
                continue
            
            try:
                with open(os.path.join(self.task_dir, filename), "r", encoding="utf-8") as f:
                    state = json.load(f)
                    if state.get("file_hash") == file_hash and state.get("status") == TaskStatus.COMPLETED:
                        return state
            except Exception:
                continue
        return None
    
    def delete_task_state(self, task_id: str) -> None:
        """删除任务状态"""
        state_path = os.path.join(self.task_dir, f"{task_id}.json")
        if os.path.exists(state_path):
            try:
                os.remove(state_path)
            except Exception as e:
                logger.warning(f"Failed to delete task state {task_id}: {e}")


# 初始化任务管理器单例
import_task_manager = ImportTaskManager()


class DocumentIngestionService:
    """文档导入服务，负责文档的解析、分块、元数据提取、索引插入"""

    def __init__(self, index_manager: IndexManagerService):
        self.index_manager = index_manager
        self.metadata_processor = MetadataProcessor()
        self.task_manager = import_task_manager

    async def ingest_book_resumable(
        self,
        file_path: str,
        original_filename: str = None,
        progress_callback: Callable[[str, float, str], None] = None,
        task_id: str = None,
        force_restart: bool = False,
        max_concurrency: int = 4,
    ) -> str:
        """
        支持断点续传的书籍导入
        :param file_path: 文件路径
        :param original_filename: 原始文件名
        :param progress_callback: 进度回调函数
        :param task_id: 任务ID，用于恢复已有任务
        :param force_restart: 是否强制重新开始，忽略已有任务状态
        :param max_concurrency: 最大并发数，用于并行处理
        :return: 文档哈希值
        """
        import uuid
        
        # 首先检查文件是否存在
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
        
        file_name = (
            original_filename if original_filename else os.path.basename(file_path)
        )
        
        # 计算文件哈希，用于幂等性校验
        file_hash = self._calculate_file_hash(file_path)
        
        # 检查是否已经导入过相同文件
        if not force_restart:
            if document_manager.exists(file_hash):
                logger.warning(
                    f"Document {file_path} already exists (hash: {file_hash}). Skipping ingestion."
                )
                return file_hash
            
            existing_task = self.task_manager.load_task_by_file_hash(file_hash)
            if existing_task:
                logger.info(f"File already imported, returning existing doc_id: {file_hash}")
                return file_hash
        
        # 加载已有任务状态
        task_state = None
        if task_id and not force_restart:
            task_state = self.task_manager.load_task_state(task_id)
            if task_state:
                logger.info(f"Resuming import task: {task_id}, progress: {task_state.get('progress', 0)}%")
                # 从断点继续处理
                return await self._resume_import_task(task_state, progress_callback, max_concurrency)
        
        # 新导入任务
        if not task_id:
            task_id = str(uuid.uuid4())
        
        logger.info(f"Starting new import task: {task_id}, file: {file_name}")
        
        task_state = {
            "task_id": task_id,
            "file_path": file_path,
            "file_name": file_name,
            "file_hash": file_hash,
            "progress": 0,
            "status": TaskStatus.RUNNING,
            "created_at": datetime.now().isoformat(),
            "current_stage": "parsing",
            "processed_sections": [],
            "max_concurrency": max_concurrency
        }
        
        # 保存初始任务状态
        self.task_manager.save_task_state(task_id, task_state)
        
        try:
            # 调用原有导入逻辑，传入任务状态
            await self._ingest_book_with_state(task_state, progress_callback)
            
            # 导入完成
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
    
    async def _resume_import_task(
        self, 
        task_state: Dict[str, Any], 
        progress_callback: Callable[[str, float, str], None] = None,
        max_concurrency: int = 4
    ) -> str:
        """从断点恢复导入任务"""
        task_id = task_state["task_id"]
        file_path = task_state["file_path"]
        file_hash = task_state["file_hash"]
        
        logger.info(f"Resuming import task {task_id} from stage: {task_state.get('current_stage', 'parsing')}")
        
        try:
            # 检查文件是否仍然存在
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"File not found: {file_path}")
            
            # 检查文件是否被修改
            current_file_hash = self._calculate_file_hash(file_path)
            if current_file_hash != file_hash:
                logger.warning("File content changed, restarting import from beginning")
                return await self.ingest_book_resumable(
                    file_path, 
                    task_state["file_name"], 
                    progress_callback, 
                    task_id, 
                    force_restart=True,
                    max_concurrency=max_concurrency
                )
            
            # 根据当前阶段继续处理
            current_stage = task_state.get("current_stage", "parsing")
            
            if current_stage == "parsing":
                # 重新开始解析
                await self._ingest_book_with_state(task_state, progress_callback)
            elif current_stage == "chunking":
                # 从分块阶段继续（需要重新解析）
                await self._ingest_book_with_state(task_state, progress_callback)
            elif current_stage == "metadata_extraction":
                # 从元数据提取阶段继续
                # TODO: 实现元数据提取断点续传
                await self._ingest_book_with_state(task_state, progress_callback)
            elif current_stage == "indexing":
                # 从索引阶段继续
                # TODO: 实现索引断点续传
                await self._ingest_book_with_state(task_state, progress_callback)
            
            # 导入完成
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
    
    async def _ingest_book_with_state(
        self,
        task_state: Dict[str, Any],
        progress_callback: Callable[[str, float, str], None] = None,
    ):
        """
        内部方法：根据任务状态执行导入流程
        """
        file_path = task_state["file_path"]
        file_name = task_state["file_name"]
        file_hash = task_state["file_hash"]
        task_id = task_state["task_id"]
        max_concurrency = task_state.get("max_concurrency", 4)
        
        try:
            # 获取PDF实际总页数
            actual_total_pages = None
            if file_path.lower().endswith(".pdf"):
                import fitz

                with fitz.open(file_path) as pdf_doc:
                    actual_total_pages = len(pdf_doc)

            # 2. 解析文档
            task_state["current_stage"] = "parsing"
            if progress_callback:
                progress_callback("parsing", 10.0, "正在解析文件")
                task_state["progress"] = 10.0
                self.task_manager.save_task_state(task_id, task_state)

            parser_cls = get_parser(file_path)
            documents = parser_cls.parse(file_path)

            # 检查PDF提取质量，必要时使用VL解析
            documents = self._check_and_use_vl_parsing(file_path, documents, parser_cls)

            if not documents:
                raise ValueError(
                    "无法从文件中提取文本。该文件可能是扫描版PDF或空文件，且无法使用VL模型识别。"
                )

            logger.info(f"Parsed {len(documents)} document chunks/pages.")

            # # 内容审核：在解析后立即审核全文内容（暂时禁用）
            # task_state["current_stage"] = "content_audit"
            # if progress_callback:
            #     progress_callback("content_audit", 20.0, "正在进行内容安全审核")
            #     task_state["progress"] = 20.0
            #     self.task_manager.save_task_state(task_id, task_state)
            
            # # 合并所有文档内容进行审核
            # full_content = "\n".join([doc.text for doc in documents])
            # audit_passed, audit_reason = await content_audit_service.audit_content(
            #     full_content, stage="import"
            # )
            # if not audit_passed:
            #     logger.warning(f"Content audit failed for {file_name}: {audit_reason}")
            #     # 内容审核失败，抛出异常中断导入流程
            #     raise ValueError(f"内容审核未通过：{audit_reason}")
            
            # logger.info(f"Content audit passed for {file_name}")

            # 计算章节数
            chapter_count = self._calculate_chapter_count(file_path, documents)

            # 4. 创建处理中的文档记录
            pending_doc = DocumentRecord(
                file_hash=file_hash,
                file_name=file_name,
                ref_doc_ids=[file_hash],
                metadata=DocumentMetadata(
                    title=file_name,
                    total_pages=(
                        actual_total_pages
                        if actual_total_pages is not None
                        else len(documents)
                    ),
                ),
                status="processing",
                progress=0.0,
            )
            document_manager.add_document(pending_doc)

            task_state["current_stage"] = "chunking"
            if progress_callback:
                progress_msg = (
                    f"文件解析完成，共{chapter_count}章"
                    if chapter_count
                    else f"文件解析完成，共{len(documents)}页"
                )
                progress_callback("chunking", 30.0, f"{progress_msg}，正在分块处理")
                # 更新pending_doc的进度
                pending_doc.progress = 30.0
                document_manager.add_document(pending_doc)
                task_state["progress"] = 30.0
                self.task_manager.save_task_state(task_id, task_state)

            # 清理文档内容
            documents = self._clean_documents(documents, file_name)

            # 检查清理后的文档是否为空
            if not documents:
                logger.error(f"No valid content found in {file_name} after cleaning")
                raise ValueError(f"文件 {file_name} 中未找到有效内容，请检查文件内容是否正常")

            # 3. 分块处理 - 优化为异步并行处理
            is_epub = file_path.lower().endswith(".epub")
            is_pdf_with_bookmarks = (
                file_path.lower().endswith(".pdf")
                and "toc_level" in documents[0].metadata
            )

            if is_epub or is_pdf_with_bookmarks:
                # 章节 + 段落分块
                file_type = "EPUB" if is_epub else "PDF with bookmarks"
                logger.info(
                    f"Using chapter + paragraph based chunking for {file_type} file"
                )
                # 包装进度回调，将章节处理进度映射到 10%-30% 区间
                def chunking_progress(stage: str, progress: float, message: str):
                    if progress_callback:
                        # 章节处理进度占 20%（10% 到 30%）
                        overall_progress = 10.0 + (progress * 0.2)
                        pending_doc.progress = overall_progress
                        document_manager.add_document(pending_doc)
                        progress_callback(stage, overall_progress, message)
                        
                        # 定期保存任务状态
                        if int(overall_progress) % 5 == 0:
                            task_state["progress"] = overall_progress
                            self.task_manager.save_task_state(task_id, task_state)
                
                all_nodes = MetadataProcessor.split_chapters_into_chunks(
                    documents,
                    chunk_target_size=settings.rag_epub_chunk_target_size,
                    file_hash=file_hash,
                    progress_callback=chunking_progress,
                )
            else:
                # 普通页面分块
                all_nodes = MetadataProcessor.split_pages_into_chunks(
                    documents,
                    chunk_size=settings.rag_pdf_chunk_size,
                    chunk_overlap=settings.rag_chunk_overlap,
                    file_hash=file_hash,
                )

            # 5. 元数据提取
            task_state["current_stage"] = "metadata_extraction"
            if progress_callback:
                progress_callback(
                    "metadata_extraction",
                    30.0,
                    f"正在提取元数据：0/{len(all_nodes)} 个块",
                )
                task_state["progress"] = 30.0
                self.task_manager.save_task_state(task_id, task_state)

            # 包装进度回调
            def wrapped_progress(stage: str, progress: float, message: str):
                if progress_callback:
                    # 元数据提取占60%进度（30%到90%）
                    overall_progress = 30.0 + (progress * 0.6)
                    pending_doc.progress = overall_progress
                    document_manager.add_document(pending_doc)
                    progress_callback(stage, overall_progress, message)
                    
                    # 定期保存任务状态（每10%进度保存一次）
                    if int(overall_progress) % 10 == 0:
                        task_state["progress"] = overall_progress
                        self.task_manager.save_task_state(task_id, task_state)

            try:
                processed_nodes = await self.metadata_processor.process_nodes(
                    all_nodes,
                    file_hash=file_hash,
                    progress_callback=wrapped_progress,
                    total_chunks=len(all_nodes),
                )
            except Exception as e:
                logger.error(
                    f"Metadata extraction failed completely: {e}", exc_info=True
                )
                # 元数据提取完全失败时使用原始节点继续，不中断导入流程
                logger.warning("Falling back to importing without metadata extraction")
                for node in all_nodes:
                    node.metadata["content"] = node.get_content()
                    node.metadata["file_hash"] = file_hash
                    node.metadata["metadata_extraction_skipped"] = True
                    # 设置默认年龄范围
                    node.metadata["target_age_min"] = 0
                    node.metadata["target_age_max"] = 18
                    node.metadata["topics"] = json.dumps([])
                    node.metadata["brain_regions"] = json.dumps([])
                    node.metadata["summary"] = ""
                    node.metadata["activity_type"] = "Theory"
                processed_nodes = all_nodes

            # 6. 索引构建
            task_state["current_stage"] = "indexing"
            if progress_callback:
                progress_callback(
                    "indexing", 90.0, f"正在插入 {len(processed_nodes)} 个节点到索引"
                )
                task_state["progress"] = 90.0
                self.task_manager.save_task_state(task_id, task_state)

            # RAG-013: 内容哈希去重
            unique_nodes = []
            existing_hashes = set()

            # 获取索引中已有的哈希 (如果索引存在)
            if self.index_manager.is_index_available():
                index = self.index_manager.get_index()
                if hasattr(index, "docstore"):
                    for node_id, node in index.docstore.docs.items():
                        if "content_hash" in node.metadata:
                            existing_hashes.add(node.metadata["content_hash"])

            for node in processed_nodes:
                content = node.get_content()
                content_hash = hashlib.sha256(content.encode()).hexdigest()
                node.metadata["content_hash"] = content_hash

                if content_hash not in existing_hashes:
                    unique_nodes.append(node)
                    existing_hashes.add(content_hash)
                else:
                    logger.info(f"Skipping duplicate node with hash: {content_hash}")

            if not unique_nodes:
                logger.info("No new unique nodes to insert. All content is duplicate.")
                # 即使没有新节点，也需要将已有节点关联到当前文档
                # 先获取所有匹配的已有节点
                if self.index_manager.is_index_available():
                    index = self.index_manager.get_index()
                    if hasattr(index, "docstore"):
                        # 找到所有content_hash匹配的已有节点
                        for node in processed_nodes:
                            content_hash = node.metadata["content_hash"]
                            # 查找docstore中匹配的节点
                            for node_id, existing_node in index.docstore.docs.items():
                                if existing_node.metadata.get("content_hash") == content_hash:
                                    # 补充当前文档的file_hash到已有节点
                                    existing_node.metadata["file_hash"] = file_hash
                                    # 保存更新
                                    index.docstore.add_documents([existing_node], allow_update=True)
                                    break
            else:
                self.index_manager.insert_nodes(
                    unique_nodes, progress_callback=progress_callback
                )

            # 7. 标记为已完成
            doc_record = DocumentRecord(
                file_hash=file_hash,
                file_name=file_name,
                ref_doc_ids=[file_hash],
                metadata=DocumentMetadata(
                    title=file_name,
                    total_pages=(
                        actual_total_pages
                        if actual_total_pages is not None
                        else len(documents)
                    ),
                    chapter_count=chapter_count,
                ),
                status="indexed",
                progress=100.0,
            )
            document_manager.add_document(doc_record)

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
            # 更新文档状态为失败
            try:
                failed_doc = DocumentRecord(
                    file_hash=file_hash,
                    file_name=file_name,
                    ref_doc_ids=[file_hash],
                    metadata=DocumentMetadata(
                        title=file_name,
                        total_pages=(
                            actual_total_pages
                            if "actual_total_pages" in locals()
                            else 0
                        ),
                    ),
                    status="failed",
                    progress=0.0,
                )
                document_manager.add_document(failed_doc)
            except:
                pass
            raise

    async def ingest_book(
        self,
        file_path: str,
        original_filename: str = None,
        progress_callback: Callable[[str, float, str], None] = None,
    ):
        """
        导入书籍文件到知识库
        Args:
            file_path: 文件路径
            original_filename: 原始文件名
            progress_callback: 进度回调函数，接收(stage: str, progress: float, message: str)参数
        """
        return await self.ingest_book_resumable(
            file_path,
            original_filename,
            progress_callback,
            force_restart=True
        )

    def _calculate_file_hash(self, file_path: str) -> str:
        """计算文件MD5哈希"""
        hash_md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()

    def _check_and_use_vl_parsing(
        self, file_path: str, documents: list, parser_cls
    ) -> list:
        """检查PDF提取质量，必要时使用VL解析，包含降级机制"""
        if parser_cls != PDFParser or not documents:
            return documents

        # 获取PDF总页数
        total_pages = documents[0].metadata.get("total_pages", len(documents))
        # 计算平均文本长度
        total_text_length = sum(len(doc.text) for doc in documents)
        avg_text_length = (
            total_text_length / len(documents) if len(documents) > 0 else 0
        )

        # 判断是否为扫描版PDF
        extraction_rate = len(documents) / total_pages if total_pages > 0 else 0
        is_scanned_pdf = (
            extraction_rate < settings.rag_ocr_extraction_rate_threshold
            or avg_text_length < settings.rag_ocr_min_avg_length_threshold
        )

        if is_scanned_pdf:
            logger.warning(
                f"PDF extraction rate low ({extraction_rate:.0%}, avg length {avg_text_length:.0f}). "
                f"Trying VL parsing for scanned PDF..."
            )
            try:
                vl_documents = PDFVLParser.parse(file_path)
                if vl_documents:
                    # 检查VL解析结果质量
                    vl_total_length = sum(len(doc.text) for doc in vl_documents)
                    vl_avg_length = (
                        vl_total_length / len(vl_documents) if vl_documents else 0
                    )

                    # 只有当VL解析质量明显优于原始提取时才使用VL结果
                    if (
                        vl_avg_length > settings.rag_ocr_min_avg_length_threshold
                        or vl_avg_length > avg_text_length * 2
                    ):
                        logger.info(
                            f"VL parsing succeeded, extracted {len(vl_documents)} pages, avg length: {vl_avg_length:.0f}"
                        )
                        return vl_documents
                    else:
                        logger.warning(
                            f"VL parsing result quality too low (avg length: {vl_avg_length:.0f}), "
                            f"falling back to original extraction (avg length: {avg_text_length:.0f})"
                        )
                else:
                    logger.warning(
                        "VL parsing returned empty results, keeping original extraction"
                    )
            except Exception as e:
                logger.error(
                    f"VL Parsing failed: {str(e)}, falling back to original extraction"
                )

        # 无论如何都返回结果，即使质量不高，避免完全失败
        logger.info(
            f"Using extraction results: {len(documents)} pages, avg length: {avg_text_length:.0f}"
        )

        # 如果所有页面都是空的，记录警告但仍继续处理
        if avg_text_length < 10:
            logger.warning(
                f"Extraction quality is very low (avg length: {avg_text_length:.0f}), "
                f"this may be a fully scanned PDF without recognizable text"
            )

        return documents

    def _calculate_chapter_count(
        self, file_path: str, documents: list
    ) -> Optional[int]:
        """计算文档的章节数"""
        is_epub = file_path.lower().endswith(".epub")
        is_pdf_with_bookmarks = (
            file_path.lower().endswith(".pdf")
            and documents
            and "toc_level" in documents[0].metadata
        )

        if is_epub or is_pdf_with_bookmarks:
            return len(documents)

        return None

    def _clean_documents(self, documents: list, file_name: str) -> list:
        """清理文档内容，移除多余空白字符"""
        cleaned_documents = []
        for doc in documents:
            # 清理多余的换行和空格
            cleaned_text = re.sub(r"\n\s*\n", "\n\n", doc.text)
            cleaned_text = re.sub(r" +", " ", cleaned_text)
            cleaned_text = cleaned_text.strip()

            # 跳过空文本的文档
            if not cleaned_text:
                logger.debug(f"Skipping empty document from {file_name}, metadata: {doc.metadata}")
                continue

            # 创建新文档
            new_doc = Document(text=cleaned_text, metadata=doc.metadata.copy())

            new_doc.metadata["file_name"] = file_name
            # 确保page_label存在
            if "page_label" not in new_doc.metadata:
                new_doc.metadata["page_label"] = new_doc.metadata.get(
                    "chapter_title", "Unknown"
                )

            cleaned_documents.append(new_doc)

        return cleaned_documents
