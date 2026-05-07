import asyncio
import json
import threading
import time
from typing import Any, Callable

from src.config import settings
from src.core.metadata_processor import MetadataProcessor
from src.service.document_manager import document_manager
from src.utils.di import get_task_state_service
from src.utils.hash_utils import content_hash as _content_hash
from src.utils.logger import logger

TASK_TYPE = "upload"


async def _safe_call_callback(callback: Callable, *args):
    """安全调用回调，支持同步和异步函数"""
    result = callback(*args)
    if asyncio.iscoroutine(result):
        await result


class _ProgressTracker:
    """线程安全的进度状态容器

    - update(): 线程侧调用（分块/Metadata 处理线程），只更新共享状态
    - consume(): event-loop 侧调用（progress_poller），原子读取+清脏标记
    """

    def __init__(self, stage: str = "chunking", progress: float = 30.0, message: str = ""):
        self._lock = threading.Lock()
        self._stage = stage
        self._progress = progress
        self._message = message
        self._dirty = False

    def update(self, stage: str, progress: float, message: str) -> None:
        with self._lock:
            self._stage = stage
            self._progress = progress
            self._message = message
            self._dirty = True

    def consume(self) -> tuple | None:
        """原子读取并清脏标记，返回 (stage, progress, message) 或 None"""
        with self._lock:
            if not self._dirty:
                return None
            self._dirty = False
            return (self._stage, self._progress, self._message)


class ChunkingAndIndexing:
    def __init__(self, index_manager):
        self.index_manager = index_manager

    async def process_chunks_and_index(
        self,
        documents: list,
        file_path: str,
        file_name: str,
        file_hash: str,
        task_id: str,
        progress_callback: Callable[[str, float, str], None] = None,
    ):
        task_state_service = get_task_state_service()
        is_epub = file_path.lower().endswith(".epub")
        is_pdf_with_bookmarks = file_path.lower().endswith(".pdf") and "toc_level" in documents[0].metadata
        loop = asyncio.get_running_loop()
        pending_doc = {
            "file_hash": file_hash,
            "file_name": file_name,
            "ref_doc_ids": [file_hash],
            "metadata": {"title": file_name, "total_pages": len(documents)},
            "status": "processing",
            "progress": 30.0,
        }
        await document_manager.add_document(pending_doc)
        if progress_callback:
            await _safe_call_callback(progress_callback, "chunking", 30.0, f"文件解析完成，正在分块处理")
        await task_state_service.update(
            task_id=task_id, task_type=TASK_TYPE,
            updates={"progress": 30.0, "stage": "chunking", "message": "文件解析完成，正在分块处理"}
        )

        if is_epub or is_pdf_with_bookmarks:
            file_type = "EPUB" if is_epub else "PDF with bookmarks"
            logger.info(f"Using chapter + paragraph based chunking for {file_type} file")

            # 创建线程安全的进度追踪器
            tracker = _ProgressTracker("chunking", 30.0, "正在分块处理")
            chunking_done = False

            async def progress_poller():
                """每 0.5s 读取 tracker 并推送到 SSE 和 Redis"""
                while not chunking_done:
                    update = tracker.consume()
                    if update and progress_callback:
                        stage, progress, message = update
                        pending_doc["progress"] = progress
                        await document_manager.add_document(pending_doc)
                        await _safe_call_callback(progress_callback, stage, progress, message)
                        await task_state_service.update(
                            task_id=task_id, task_type=TASK_TYPE,
                            updates={"progress": progress, "stage": stage, "message": message}
                        )
                    await asyncio.sleep(0.5)
                # 最后一次刷新
                update = tracker.consume()
                if update and progress_callback:
                    stage, progress, message = update
                    pending_doc["progress"] = progress
                    await document_manager.add_document(pending_doc)
                    await _safe_call_callback(progress_callback, stage, progress, message)
                    await task_state_service.update(
                        task_id=task_id, task_type=TASK_TYPE,
                        updates={"progress": progress, "stage": stage, "message": message}
                    )

            poller = asyncio.create_task(progress_poller())

            try:
                t_chunk_start = time.monotonic()
                all_nodes = await asyncio.to_thread(
                    MetadataProcessor.split_chapters_into_chunks,
                    documents, chunk_target_size=settings.rag_epub_chunk_target_size,
                    file_hash=file_hash,
                    progress_callback=lambda s, p, m: tracker.update(
                        s, 30.0 + (p / 100.0 * 20.0), m
                    ),
                )
            finally:
                chunking_done = True
                await poller

            logger.info(f"[PERF] chunking ({file_type}): {time.monotonic() - t_chunk_start:.2f}s, {len(all_nodes)} nodes from {len(documents)} chapters")
        else:
            # PDF: 使用线程安全的进度追踪器（此前缺失进度回调！）
            tracker = _ProgressTracker("chunking", 30.0, "正在分块处理")
            chunking_done = False

            async def progress_poller():
                """每 0.5s 读取 tracker 并推送"""
                while not chunking_done:
                    update = tracker.consume()
                    if update and progress_callback:
                        stage, progress, message = update
                        pending_doc["progress"] = progress
                        await document_manager.add_document(pending_doc)
                        await _safe_call_callback(progress_callback, stage, progress, message)
                        await task_state_service.update(
                            task_id=task_id, task_type=TASK_TYPE,
                            updates={"progress": progress, "stage": stage, "message": message}
                        )
                    await asyncio.sleep(0.5)
                update = tracker.consume()
                if update and progress_callback:
                    stage, progress, message = update
                    pending_doc["progress"] = progress
                    await document_manager.add_document(pending_doc)
                    await _safe_call_callback(progress_callback, stage, progress, message)
                    await task_state_service.update(
                        task_id=task_id, task_type=TASK_TYPE,
                        updates={"progress": progress, "stage": stage, "message": message}
                    )

            poller = asyncio.create_task(progress_poller())

            try:
                t_chunk_start = time.monotonic()
                all_nodes = await loop.run_in_executor(
                    None,
                    MetadataProcessor.split_pages_into_chunks,
                    documents, settings.rag_pdf_chunk_size,
                    settings.rag_chunk_overlap, file_hash,
                    lambda s, p, m: tracker.update(
                        s, 30.0 + (p / 100.0 * 20.0), m
                    ),
                )
            finally:
                chunking_done = True
                await poller

            logger.info(f"[PERF] chunking (page-based): {time.monotonic() - t_chunk_start:.2f}s, {len(all_nodes)} nodes from {len(documents)} pages")

        if progress_callback:
            await _safe_call_callback(progress_callback, "metadata_extraction", 30.0, f"正在提取元数据：0/{len(all_nodes)} 个块")
        await task_state_service.update(
            task_id=task_id, task_type=TASK_TYPE,
            updates={"progress": 30.0, "stage": "metadata_extraction", "message": f"正在提取元数据：0/{len(all_nodes)} 个块"}
        )

        def wrapped_progress(stage: str, progress: float, message: str):
            nonlocal pending_doc
            if progress_callback:
                overall_progress = 30.0 + (progress * 0.6)
                pending_doc["progress"] = overall_progress
                asyncio.run_coroutine_threadsafe(
                    document_manager.add_document(pending_doc), loop
                )
                res = progress_callback(stage, overall_progress, message)
                if asyncio.iscoroutine(res):
                    asyncio.run_coroutine_threadsafe(res, loop)

        metadata_processor = MetadataProcessor()
        try:
            t_meta_start = time.monotonic()
            processed_nodes = await metadata_processor.process_nodes(
                all_nodes, file_hash=file_hash, progress_callback=wrapped_progress, total_chunks=len(all_nodes),
            )
            logger.info(f"[PERF] metadata_extraction: {time.monotonic() - t_meta_start:.2f}s, {len(processed_nodes)} nodes")
        except Exception as e:
            logger.error(f"Metadata extraction failed completely: {e}", exc_info=True)
            logger.warning("Falling back to importing without metadata extraction")
            for node in all_nodes:
                node.metadata["content"] = node.get_content()
                node.metadata["file_hash"] = file_hash
                node.metadata["metadata_extraction_skipped"] = True
                node.metadata["topics"] = json.dumps([])
                node.metadata["brain_regions"] = json.dumps([])
                node.metadata["summary"] = ""
                node.metadata["activity_type"] = "Theory"
            processed_nodes = all_nodes

        if progress_callback:
            await _safe_call_callback(progress_callback, "indexing", 90.0, f"正在插入 {len(processed_nodes)} 个节点到索引")
        await task_state_service.update(
            task_id=task_id, task_type=TASK_TYPE,
            updates={"progress": 90.0, "stage": "indexing", "message": f"正在插入 {len(processed_nodes)} 个节点到索引"}
        )

        unique_nodes = []
        existing_hashes = set()

        t_dedup_start = time.monotonic()
        if self.index_manager.is_index_available():
            index = self.index_manager.get_index()
            if hasattr(index, "docstore"):
                # 只收集content_hash，不存储完整Node对象引用，避免内存溢出
                for node_id, node in index.docstore.docs.items():
                    if "content_hash" in node.metadata:
                        existing_hashes.add(node.metadata["content_hash"])

        for node in processed_nodes:
            content = node.get_content()
            ch = _content_hash(content)
            node.metadata["content_hash"] = ch
            if ch not in existing_hashes:
                unique_nodes.append(node)
                existing_hashes.add(ch)
            else:
                logger.info(f"Skipping duplicate node with hash: {ch}")
        
        # 去重完成后清理内存
        import gc
        gc.collect()
        logger.info(f"[PERF] dedup: {time.monotonic() - t_dedup_start:.2f}s, {len(unique_nodes)} unique / {len(processed_nodes)} total")

        cancelled = False

        if not unique_nodes:
            logger.info("No new unique nodes to insert. All content is duplicate.")
            # 重新遍历docstore更新重复节点的file_hash，避免存储完整Node对象
            if self.index_manager.is_index_available():
                index = self.index_manager.get_index()
                if hasattr(index, "docstore"):
                    update_nodes = []
                    for node_id, existing_node in index.docstore.docs.items():
                        if existing_node.metadata.get("content_hash") in existing_hashes:
                            existing_node.metadata["file_hash"] = file_hash
                            update_nodes.append(existing_node)
                    
                    if update_nodes:
                        index.docstore.add_documents(update_nodes, allow_update=True)
                        logger.info(f"Updated file_hash for {len(update_nodes)} duplicate nodes")
            
            # 释放不再需要的集合
            del existing_hashes
        else:
            # 可选：使用异步批量 API 预计算嵌入，分批处理避免内存溢出
            if settings.embedding_use_async_batch and len(unique_nodes) > settings.embedding_async_batch_threshold:
                from src.core.embedding_batch import batch_embed_texts_smart
                import gc

                logger.info(
                    f"Pre-computing embeddings using async batch API for {len(unique_nodes)} nodes..."
                )
                t_embed_start = time.monotonic()
                
                # 分批处理嵌入，使用配置值避免一次性加载所有文本到内存
                EMBED_BATCH_SIZE = settings.rag_index_insert_batch_size
                for i in range(0, len(unique_nodes), EMBED_BATCH_SIZE):
                    batch_nodes = unique_nodes[i:i + EMBED_BATCH_SIZE]
                    texts = [node.get_content() for node in batch_nodes]
                    
                    try:
                        batch_embeddings = await batch_embed_texts_smart(texts, threshold=settings.embedding_async_batch_threshold)
                        for node, embedding in zip(batch_nodes, batch_embeddings):
                            node.embedding = embedding
                    finally:
                        # 每批处理完后立即清理，释放内存
                        del texts
                        if 'batch_embeddings' in locals():
                            del batch_embeddings
                        gc.collect()
                    
                    # 每批处理后报告进度
                    if progress_callback:
                        batch_progress = 90.0 + ((i + len(batch_nodes)) / len(unique_nodes)) * 9.0
                        await _safe_call_callback(progress_callback, "embedding", batch_progress, f"正在计算嵌入向量：{i + len(batch_nodes)}/{len(unique_nodes)} 个块")
                
                logger.info("Pre-computed embeddings for all nodes")
                logger.info(f"[PERF] embedding: {time.monotonic() - t_embed_start:.2f}s")

            # 将同步的索引操作放入线程池执行，避免阻塞事件循环，添加取消检查和进度更新
            indexing_completed = False
            t_index_start = time.monotonic()

            def check_cancellation():
                nonlocal cancelled
                if progress_callback:
                    try:
                        res = progress_callback("indexing", 95.0, "正在插入到索引中")
                        if asyncio.iscoroutine(res):
                            asyncio.run_coroutine_threadsafe(res, loop)
                    except Exception:
                        cancelled = True
                return cancelled
            
            def wrapped_insert():
                nonlocal indexing_completed
                batch_size = settings.rag_index_insert_batch_size
                total_nodes = len(unique_nodes)
                
                # 批量插入节点，大幅提升性能
                for i in range(0, total_nodes, batch_size):
                    if check_cancellation():
                        break
                    
                    batch = unique_nodes[i:i + batch_size]
                    batch_num = (i // batch_size) + 1
                    total_batches = (total_nodes + batch_size - 1) // batch_size
                    
                    try:
                        self.index_manager.insert_nodes(batch, progress_callback=None)
                    except Exception as batch_error:
                        logger.error(f"Failed to insert batch {batch_num}: {batch_error}")
                        if len(batch) == 1:
                            logger.warning(f"Skipping failed node at index {i}: {str(batch_error)[:200]}")
                        else:
                            raise
                    
                    # 每批次更新进度
                    if progress_callback:
                        progress = 90.0 + ((i + len(batch)) / total_nodes) * 9.0
                        res = progress_callback("indexing", progress, f"正在插入批次 {batch_num}/{total_batches}")
                        if asyncio.iscoroutine(res):
                            asyncio.run_coroutine_threadsafe(res, loop)
                
                indexing_completed = True
            
            await loop.run_in_executor(None, wrapped_insert)
            logger.info(f"[PERF] index_insert: {time.monotonic() - t_index_start:.2f}s, {len(unique_nodes)} nodes")
            
        # 索引构建完成后清理内存
        gc.collect()
        
        if cancelled:
            from src.utils.exceptions import TaskCancelledException
            raise TaskCancelledException("Task cancelled during indexing")

        # 索引构建完成，更新最后一次进度
        if progress_callback:
            await _safe_call_callback(progress_callback, "indexing", 99.0, "索引构建完成，正在保存数据")
        await task_state_service.update(
            task_id=task_id, task_type=TASK_TYPE,
            updates={"progress": 99.0, "stage": "indexing", "message": "索引构建完成，正在保存数据"}
        )
        
        return pending_doc, len(documents)
