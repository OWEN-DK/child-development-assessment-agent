import os
import hashlib
import re
import asyncio
from typing import Optional, Callable
from llama_index.core.schema import Document
from src.config.settings import settings
from src.utils.logger import logger
from src.utils.exceptions import TaskCancelledException
from src.core.parsers import get_parser, PDFParser, PDFVLParser
from src.core.metadata_processor import MetadataProcessor
from src.model.document import DocumentRecord, DocumentMetadata
from src.service.document_manager import document_manager
from src.service.index_manager_service import IndexManagerService
from src.service.retrieval_service import RetrievalService


class DocumentIngestionService:
    """文档导入服务，负责文档的解析、分块、元数据提取、索引插入"""

    def __init__(
        self, index_manager: IndexManagerService, retrieval_service: RetrievalService
    ):
        self.index_manager = index_manager
        self.retrieval_service = retrieval_service
        self.metadata_processor = MetadataProcessor()

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
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        file_name = (
            original_filename if original_filename else os.path.basename(file_path)
        )
        logger.info(f"Ingesting book: {file_path} as {file_name}")

        # 1. 去重检查
        file_hash = self._calculate_file_hash(file_path)
        if document_manager.exists(file_hash):
            logger.warning(
                f"Document {file_path} already exists (hash: {file_hash}). Skipping ingestion."
            )
            return

        try:
            # 获取PDF实际总页数
            actual_total_pages = None
            if file_path.lower().endswith(".pdf"):
                import fitz

                with fitz.open(file_path) as pdf_doc:
                    actual_total_pages = len(pdf_doc)

            # 2. 解析文档
            if progress_callback:
                progress_callback("parsing", 10.0, "正在解析文件")

            parser_cls = get_parser(file_path)
            documents = parser_cls.parse(file_path)

            # 检查PDF提取质量，必要时使用VL解析
            documents = self._check_and_use_vl_parsing(file_path, documents, parser_cls)

            if not documents:
                raise ValueError(
                    "无法从文件中提取文本。该文件可能是扫描版PDF或空文件，且无法使用VL模型识别。"
                )

            logger.info(f"Parsed {len(documents)} document chunks/pages.")

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

            # 清理文档内容
            documents = self._clean_documents(documents, file_name)

            # 3. 分块处理
            is_epub = file_path.lower().endswith(".epub")
            is_pdf_with_bookmarks = (
                file_path.lower().endswith(".pdf")
                and documents
                and "toc_level" in documents[0].metadata
            )

            if is_epub or is_pdf_with_bookmarks:
                # 章节+段落分块
                file_type = "EPUB" if is_epub else "PDF with bookmarks"
                logger.info(
                    f"Using chapter + paragraph based chunking for {file_type} file"
                )
                all_nodes = MetadataProcessor.split_chapters_into_chunks(
                    documents,
                    chunk_target_size=settings.rag_epub_chunk_target_size,
                    file_hash=file_hash,
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
            if progress_callback:
                progress_callback(
                    "metadata_extraction",
                    30.0,
                    f"正在提取元数据：0/{len(all_nodes)} 个块",
                )

            # 包装进度回调
            def wrapped_progress(stage: str, progress: float, message: str):
                if progress_callback:
                    # 元数据提取占60%进度（30%到90%）
                    overall_progress = 30.0 + (progress * 0.6)
                    pending_doc.progress = overall_progress
                    document_manager.add_document(pending_doc)
                    progress_callback(stage, overall_progress, message)

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
                    node.metadata["topics"] = []
                    node.metadata["brain_regions"] = []
                    node.metadata["summary"] = ""
                    node.metadata["activity_type"] = "Theory"
                processed_nodes = all_nodes

            # 6. 索引构建
            if progress_callback:
                progress_callback(
                    "indexing", 90.0, f"正在插入 {len(processed_nodes)} 个节点到索引"
                )

            self.index_manager.insert_nodes(
                processed_nodes, progress_callback=progress_callback
            )

            # 重新加载检索器
            self.retrieval_service.reload_retrievers()

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
