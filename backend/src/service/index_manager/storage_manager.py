import os
import shutil
import threading
import time
from typing import Callable, List, Optional

from llama_index.core import (StorageContext, VectorStoreIndex,
                              load_index_from_storage)
from llama_index.core.schema import Node

from src.config import settings
from src.core.vector_store_factory import VectorStoreFactory
from src.service.document_manager import document_manager
from src.utils.logger import logger

STORAGE_DIR = settings.rag_storage_dir


class StorageManager:
    def __init__(self):
        self.index: Optional[VectorStoreIndex] = None
        self._dirty = False
        self._persist_thread = None
        self._stop_persist_thread = threading.Event()
        self._initialize_index()
        self._start_auto_persist()

    def _initialize_index(self):
        index_dir = os.path.join(STORAGE_DIR, "index")
        if not os.path.exists(index_dir):
            os.makedirs(index_dir, exist_ok=True)
        max_retries = 3
        retry_delay = 1
        try:
            vector_store = VectorStoreFactory.get_vector_store()
            logger.info(f"Using vector store type: {settings.vector_store_type}")
        except Exception as e:
            logger.error(f"Failed to initialize vector store: {e}")
            raise
        for attempt in range(max_retries):
            try:
                if os.path.exists(os.path.join(index_dir, "docstore.json")):
                    logger.info(f"Loading index from storage (attempt {attempt + 1}/{max_retries})...")
                    storage_context = StorageContext.from_defaults(persist_dir=index_dir, vector_store=vector_store)
                    self.index = load_index_from_storage(storage_context)
                    logger.info("Index loaded successfully.")
                    return
                else:
                    logger.warning("No existing index found (missing docstore.json). Waiting for file uploads.")
                    if settings.vector_store_type == "chroma" and "collection_name" in settings.vector_store_config:
                        logger.info("Attempting to load from Chroma vector store directly")
                        try:
                            storage_context = StorageContext.from_defaults(vector_store=vector_store)
                            self.index = VectorStoreIndex.from_vector_store(vector_store, storage_context=storage_context)
                            logger.info("Successfully created index from existing vector store")
                            return
                        except Exception as vc_e:
                            logger.warning(f"Failed to load from vector store: {vc_e}")
                    self.index = None
                    return
            except Exception as e:
                logger.error(f"Failed to load index from storage (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt == max_retries - 1:
                    backup_dir = f"{index_dir}.bak"
                    if os.path.exists(backup_dir) and os.path.exists(os.path.join(backup_dir, "docstore.json")):
                        logger.info(f"Trying to restore from backup: {backup_dir}")
                        try:
                            storage_context = StorageContext.from_defaults(persist_dir=backup_dir)
                            self.index = load_index_from_storage(storage_context)
                            logger.info("Index restored from backup successfully.")
                            self._persist_index()
                            return
                        except Exception as backup_error:
                            logger.error(f"Failed to restore from backup: {backup_error}")
                    logger.error("All index loading attempts failed. Starting with empty index.")
                    if os.path.exists(index_dir):
                        corrupted_dir = f"{index_dir}.corrupted.{int(time.time())}"
                        try:
                            os.rename(index_dir, corrupted_dir)
                            logger.info(f"Corrupted index directory moved to: {corrupted_dir}")
                        except Exception as rename_error:
                            logger.error(f"Failed to move corrupted directory: {rename_error}")
                            shutil.rmtree(index_dir)
                    os.makedirs(index_dir, exist_ok=True)
                    self.index = None
                    return
                time.sleep(retry_delay * (2**attempt))

    def _start_auto_persist(self):
        if hasattr(settings, "rag_auto_persist_enabled") and settings.rag_auto_persist_enabled:
            interval = getattr(settings, "rag_auto_persist_interval", 300)
            self._persist_thread = threading.Thread(target=self._auto_persist_worker, daemon=False)
            self._persist_thread.start()
            logger.info(f"Auto-persist thread started, interval: {interval}s")

    def _auto_persist_worker(self):
        interval = getattr(settings, "rag_auto_persist_interval", 300)
        while not self._stop_persist_thread.is_set():
            if self._dirty and self.index is not None:
                try:
                    self._persist_index()
                    self._dirty = False
                    logger.debug("Auto-persisted index changes")
                except Exception as e:
                    logger.error(f"Auto-persist failed: {e}")
            self._stop_persist_thread.wait(interval)

    def _persist_index(self):
        if self.index:
            index_dir = os.path.join(STORAGE_DIR, "index")
            temp_dir = f"{index_dir}.tmp"
            backup_dir = f"{index_dir}.bak"
            try:
                if os.path.exists(temp_dir):
                    shutil.rmtree(temp_dir)
                os.makedirs(temp_dir, exist_ok=True)
                if hasattr(self.index, 'docstore') and self.index.docstore:
                    import json
                    import gc
                    docstore_path = os.path.join(temp_dir, "docstore.json")
                    
                    # 流式写入docstore.json，避免在内存中构建完整字典
                    with open(docstore_path, 'w', encoding='utf-8') as f:
                        f.write('{"docs": {')
                        first = True
                        count = 0
                        
                        for doc_id, node in self.index.docstore.docs.items():
                            if not first:
                                f.write(',')
                            first = False
                            
                            # 构建单个节点的JSON并直接写入
                            node_data = {
                                "id": doc_id,
                                "text": node.text,
                                "metadata": node.metadata,
                                "start_char_idx": node.start_char_idx,
                                "end_char_idx": node.end_char_idx,
                                "relationships": {
                                    k.value: {"node_id": v.node_id} if hasattr(v, 'node_id') else str(v)
                                    for k, v in node.relationships.items()
                                } if node.relationships else {}
                            }
                            
                            # 直接写入JSON，避免中间字典
                            f.write(f'\n"{doc_id}": ')
                            json.dump(node_data, f, ensure_ascii=False)
                            count += 1
                            
                            # 每处理1000个节点清理一次内存
                            if count % 1000 == 0:
                                gc.collect()
                        
                        f.write('\n}}')
                    
                    logger.info(f"Manually persisted {count} documents to docstore.json")
                    # 释放大对象
                    del count
                    gc.collect()
                self.index.storage_context.persist(persist_dir=temp_dir)
                if os.path.exists(index_dir):
                    if os.path.exists(backup_dir):
                        shutil.rmtree(backup_dir)
                    os.rename(index_dir, backup_dir)
                os.rename(temp_dir, index_dir)
                if os.path.exists(backup_dir):
                    shutil.rmtree(backup_dir)
                from src.core.event_bus import IndexUpdateEvent, event_bus
                event_bus.publish(IndexUpdateEvent("index"))
                logger.debug("Index persisted to disk atomically, update event published")
            except Exception as e:
                logger.error(f"Failed to persist index: {e}")
                if os.path.exists(backup_dir) and not os.path.exists(index_dir):
                    try:
                        os.rename(backup_dir, index_dir)
                        logger.info("Successfully rolled back to previous index version")
                    except Exception as rollback_error:
                        logger.error(f"Failed to rollback index: {rollback_error}")
                raise

    def _clear_index(self):
        logger.info("All documents deleted, clearing entire index")
        self.index = None
        self._dirty = False
        index_dir = os.path.join(STORAGE_DIR, "index")
        if os.path.exists(index_dir):
            shutil.rmtree(index_dir)
            os.makedirs(index_dir, exist_ok=True)
        backup_dir = f"{index_dir}.bak"
        temp_dir = f"{index_dir}.tmp"
        for dir_path in [backup_dir, temp_dir]:
            if os.path.exists(dir_path):
                shutil.rmtree(dir_path)
        logger.info("Index and storage cleared completely")

    def get_index(self) -> Optional[VectorStoreIndex]:
        return self.index

    def is_index_available(self) -> bool:
        return self.index is not None

    def get_corpus_size(self) -> int:
        if not self.index:
            return 0
        if hasattr(self.index, '_vector_store') and self.index._vector_store:
            vector_store = self.index._vector_store
            if hasattr(vector_store, '_collection') and vector_store._collection:
                try:
                    return vector_store._collection.count()
                except:
                    pass
        if hasattr(self.index, 'docstore'):
            return len(self.index.docstore.docs)
        return 0

    def shutdown(self):
        if hasattr(self, "_stop_persist_thread"):
            self._stop_persist_thread.set()
        if hasattr(self, "_persist_thread") and self._persist_thread is not None and self._persist_thread.is_alive():
            self._persist_thread.join(timeout=5)
        if hasattr(self, "_dirty") and self._dirty and self.index is not None:
            try:
                self._persist_index()
                logger.info("Persisted index changes on shutdown")
            except Exception as e:
                logger.error(f"Failed to persist index on shutdown: {e}")
