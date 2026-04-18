import asyncio
import json
from typing import Any, Callable, Dict

from src.config import settings
from src.core.metadata_processor import MetadataProcessor
from src.schemas import DocumentMetadata, DocumentRecord
from src.service.document_manager import document_manager
from src.utils.logger import logger


class ChunkingAndIndexing:
    def __init__(self, index_manager, task_manager):
        self.index_manager = index_manager
        self.task_manager = task_manager

    async def process_chunks_and_index(
        self,
        documents: list,
        file_path: str,
        file_name: str,
        file_hash: str,
        task_id: str,
        task_state: Dict[str, Any],
        progress_callback: Callable[[str, float, str], None] = None,
    ):
        is_epub = file_path.lower().endswith(".epub")
        is_pdf_with_bookmarks = file_path.lower().endswith(".pdf") and "toc_level" in documents[0].metadata
        pending_doc = DocumentRecord(
            file_hash=file_hash, file_name=file_name, ref_doc_ids=[file_hash],
            metadata=DocumentMetadata(title=file_name, total_pages=len(documents)),
            status="processing", progress=30.0,
        )
        document_manager.add_document(pending_doc)
        task_state["current_stage"] = "chunking"
        if progress_callback:
            progress_callback("chunking", 30.0, f"文件解析完成，正在分块处理")
            task_state["progress"] = 30.0
            self.task_manager.save_task_state(task_id, task_state)

        if is_epub or is_pdf_with_bookmarks:
            file_type = "EPUB" if is_epub else "PDF with bookmarks"
            logger.info(f"Using chapter + paragraph based chunking for {file_type} file")
            def chunking_progress(stage: str, progress: float, message: str):
                if progress_callback:
                    overall_progress = 10.0 + (progress * 0.2)
                    pending_doc.progress = overall_progress
                    document_manager.add_document(pending_doc)
                    progress_callback(stage, overall_progress, message)
                    if int(overall_progress) % 5 == 0:
                        task_state["progress"] = overall_progress
                        self.task_manager.save_task_state(task_id, task_state)
            all_nodes = MetadataProcessor.split_chapters_into_chunks(
                documents, chunk_target_size=settings.rag_epub_chunk_target_size,
                file_hash=file_hash, progress_callback=chunking_progress,
            )
        else:
            all_nodes = MetadataProcessor.split_pages_into_chunks(
                documents, chunk_size=settings.rag_pdf_chunk_size,
                chunk_overlap=settings.rag_chunk_overlap, file_hash=file_hash,
            )

        task_state["current_stage"] = "metadata_extraction"
        if progress_callback:
            progress_callback("metadata_extraction", 30.0, f"正在提取元数据：0/{len(all_nodes)} 个块")
            task_state["progress"] = 30.0
            self.task_manager.save_task_state(task_id, task_state)

        def wrapped_progress(stage: str, progress: float, message: str):
            if progress_callback:
                overall_progress = 30.0 + (progress * 0.6)
                pending_doc.progress = overall_progress
                document_manager.add_document(pending_doc)
                progress_callback(stage, overall_progress, message)
                if int(overall_progress) % 10 == 0:
                    task_state["progress"] = overall_progress
                    self.task_manager.save_task_state(task_id, task_state)

        metadata_processor = MetadataProcessor()
        try:
            processed_nodes = await metadata_processor.process_nodes(
                all_nodes, file_hash=file_hash, progress_callback=wrapped_progress, total_chunks=len(all_nodes),
            )
        except Exception as e:
            logger.error(f"Metadata extraction failed completely: {e}", exc_info=True)
            logger.warning("Falling back to importing without metadata extraction")
            for node in all_nodes:
                node.metadata["content"] = node.get_content()
                node.metadata["file_hash"] = file_hash
                node.metadata["metadata_extraction_skipped"] = True
                node.metadata["target_age_min"] = 0
                node.metadata["target_age_max"] = 18
                node.metadata["topics"] = json.dumps([])
                node.metadata["brain_regions"] = json.dumps([])
                node.metadata["summary"] = ""
                node.metadata["activity_type"] = "Theory"
            processed_nodes = all_nodes

        task_state["current_stage"] = "indexing"
        if progress_callback:
            progress_callback("indexing", 90.0, f"正在插入 {len(processed_nodes)} 个节点到索引")
            task_state["progress"] = 90.0
            self.task_manager.save_task_state(task_id, task_state)

        import hashlib
        unique_nodes = []
        existing_hashes = set()
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
            if self.index_manager.is_index_available():
                index = self.index_manager.get_index()
                if hasattr(index, "docstore"):
                    for node in processed_nodes:
                        content_hash = node.metadata["content_hash"]
                        for node_id, existing_node in index.docstore.docs.items():
                            if existing_node.metadata.get("content_hash") == content_hash:
                                existing_node.metadata["file_hash"] = file_hash
                                index.docstore.add_documents([existing_node], allow_update=True)
                                break
        else:
            self.index_manager.insert_nodes(unique_nodes, progress_callback=progress_callback)

        return pending_doc, len(documents)
