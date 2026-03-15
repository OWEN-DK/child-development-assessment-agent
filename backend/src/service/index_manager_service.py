import os
import threading
import time
import shutil
from typing import Optional, Callable
from llama_index.core import (
    VectorStoreIndex,
    StorageContext,
    load_index_from_storage,
    Settings,
)
from llama_index.core.schema import Node
from src.config.settings import settings
from src.utils.logger import logger
from src.service.document_manager import document_manager

STORAGE_DIR = settings.rag_storage_dir


class IndexManagerService:
    """索引管理服务，负责索引的初始化、加载、更新、持久化"""

    def __init__(self):
        self.index: Optional[VectorStoreIndex] = None
        self._dirty = False  # 索引是否有未持久化的更改
        self._persist_thread = None
        self._stop_persist_thread = threading.Event()
        self._initialize_index()
        self._start_auto_persist()

    def _initialize_index(self):
        """从存储中初始化向量索引，带有重试机制和备份恢复"""
        if not os.path.exists(STORAGE_DIR):
            os.makedirs(STORAGE_DIR)

        max_retries = 3
        retry_delay = 1  # 秒

        for attempt in range(max_retries):
            try:
                if os.path.exists(os.path.join(STORAGE_DIR, "docstore.json")):
                    logger.info(
                        f"Loading index from storage (attempt {attempt + 1}/{max_retries})..."
                    )
                    storage_context = StorageContext.from_defaults(
                        persist_dir=STORAGE_DIR
                    )
                    self.index = load_index_from_storage(storage_context)
                    logger.info("Index loaded successfully.")
                    return
                else:
                    logger.warning("No existing index found. Waiting for file uploads.")
                    self.index = None
                    return
            except Exception as e:
                logger.error(
                    f"Failed to load index from storage (attempt {attempt + 1}/{max_retries}): {e}"
                )

                # 最后一次尝试失败，尝试从备份恢复
                if attempt == max_retries - 1:
                    backup_dir = f"{STORAGE_DIR}.bak"
                    if os.path.exists(backup_dir) and os.path.exists(
                        os.path.join(backup_dir, "docstore.json")
                    ):
                        logger.info(f"Trying to restore from backup: {backup_dir}")
                        try:
                            storage_context = StorageContext.from_defaults(
                                persist_dir=backup_dir
                            )
                            self.index = load_index_from_storage(storage_context)
                            logger.info("Index restored from backup successfully.")
                            # 恢复后重写主存储
                            self._persist_index()
                            return
                        except Exception as backup_error:
                            logger.error(
                                f"Failed to restore from backup: {backup_error}"
                            )

                    # 所有尝试都失败，清空损坏的存储
                    logger.error(
                        "All index loading attempts failed. Starting with empty index."
                    )
                    # 重命名损坏的目录以便排查
                    if os.path.exists(STORAGE_DIR):
                        corrupted_dir = f"{STORAGE_DIR}.corrupted.{int(time.time())}"
                        try:
                            os.rename(STORAGE_DIR, corrupted_dir)
                            logger.info(
                                f"Corrupted index directory moved to: {corrupted_dir}"
                            )
                        except Exception as rename_error:
                            logger.error(
                                f"Failed to move corrupted directory: {rename_error}"
                            )
                            # 如果重命名失败，直接删除
                            shutil.rmtree(STORAGE_DIR)

                    os.makedirs(STORAGE_DIR, exist_ok=True)
                    self.index = None
                    return

                # 等待后重试，指数退避
                time.sleep(retry_delay * (2**attempt))

    def _start_auto_persist(self):
        """启动自动持久化线程"""
        if (
            hasattr(settings, "rag_auto_persist_enabled")
            and settings.rag_auto_persist_enabled
        ):
            interval = getattr(settings, "rag_auto_persist_interval", 300)
            self._persist_thread = threading.Thread(
                target=self._auto_persist_worker, daemon=True
            )
            self._persist_thread.start()
            logger.info(f"Auto-persist thread started, interval: {interval}s")

    def _auto_persist_worker(self):
        """自动持久化工作线程"""
        interval = getattr(settings, "rag_auto_persist_interval", 300)
        while not self._stop_persist_thread.is_set():
            if self._dirty and self.index is not None:
                try:
                    self._persist_index()
                    self._dirty = False
                    logger.debug("Auto-persisted index changes")
                except Exception as e:
                    logger.error(f"Auto-persist failed: {e}")

            # 等待指定间隔
            self._stop_persist_thread.wait(interval)

    def insert_nodes(
        self,
        nodes: list[Node],
        progress_callback: Callable[[str, float, str], None] = None,
    ):
        """插入节点到索引"""
        logger.info(f"Starting index insertion for {len(nodes)} nodes")

        if not self.index:
            if progress_callback:
                progress_callback(
                    "indexing", 92.0, f"正在创建新索引，共 {len(nodes)} 个节点"
                )
            logger.info("Creating new VectorStoreIndex from nodes")
            # 创建新索引
            self.index = VectorStoreIndex(nodes)
            logger.info("New index created successfully")
        else:
            if progress_callback:
                progress_callback(
                    "indexing", 92.0, f"正在插入 {len(nodes)} 个节点到现有索引"
                )
            logger.info("Inserting nodes into existing index")
            # 增量插入
            self.index.insert_nodes(nodes)
            logger.info("Nodes inserted successfully")

        # 标记为需要持久化
        self._dirty = True

        if progress_callback:
            progress_callback("indexing", 95.0, "正在持久化索引到磁盘")

        logger.info("Starting index persistence")
        # 立即持久化关键操作
        self._persist_index()
        self._dirty = False
        logger.info("Index persisted successfully")

        if progress_callback:
            progress_callback("indexing", 98.0, "索引构建完成")

        logger.info(f"Successfully inserted {len(nodes)} nodes into index")

    def delete_document(self, file_name: str) -> bool:
        """根据文件名删除文档"""
        doc = document_manager.get_document_by_name(file_name)
        if not doc:
            logger.warning(f"Document {file_name} not found in registry.")
            return False

        # 无论索引是否初始化，都要从文档管理器中删除记录
        if not self.index:
            logger.warning("Index not initialized, only deleting document record.")
            document_manager.delete_document(doc.file_hash)
            return True

        logger.info(f"Deleting document: {file_name} (hash: {doc.file_hash})")

        try:
            # 删除索引中的文档
            for ref_id in doc.ref_doc_ids:
                self.index.delete_ref_doc(ref_id, delete_from_docstore=True)

            # 立即持久化
            self._persist_index()
            self._dirty = False
            document_manager.delete_document(doc.file_hash)

            # 如果是最后一个文档，清空索引
            remaining_docs = document_manager.list_documents()
            if not remaining_docs:
                self._clear_index()

            logger.info(f"Successfully deleted {file_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete document: {e}")
            return False

    def _persist_index(self):
        """持久化索引到磁盘，使用原子写入和备份机制"""
        if self.index:
            # 创建临时目录进行原子写入
            temp_dir = f"{STORAGE_DIR}.tmp"
            backup_dir = f"{STORAGE_DIR}.bak"

            try:
                # 先写入到临时目录
                if os.path.exists(temp_dir):
                    shutil.rmtree(temp_dir)
                os.makedirs(temp_dir, exist_ok=True)

                self.index.storage_context.persist(persist_dir=temp_dir)

                # 备份现有目录
                if os.path.exists(STORAGE_DIR):
                    if os.path.exists(backup_dir):
                        shutil.rmtree(backup_dir)
                    os.rename(STORAGE_DIR, backup_dir)

                # 替换为新目录
                os.rename(temp_dir, STORAGE_DIR)

                # 清理备份
                if os.path.exists(backup_dir):
                    shutil.rmtree(backup_dir)

                logger.debug("Index persisted to disk atomically")
            except Exception as e:
                logger.error(f"Failed to persist index: {e}")
                # 回滚
                if os.path.exists(backup_dir) and not os.path.exists(STORAGE_DIR):
                    try:
                        os.rename(backup_dir, STORAGE_DIR)
                        logger.info(
                            "Successfully rolled back to previous index version"
                        )
                    except Exception as rollback_error:
                        logger.error(f"Failed to rollback index: {rollback_error}")
                raise

    def _clear_index(self):
        """清空索引和存储"""
        logger.info("All documents deleted, clearing entire index")
        self.index = None
        self._dirty = False
        # 删除存储目录
        if os.path.exists(STORAGE_DIR):
            shutil.rmtree(STORAGE_DIR)
            os.makedirs(STORAGE_DIR, exist_ok=True)
        # 清理备份文件
        backup_dir = f"{STORAGE_DIR}.bak"
        temp_dir = f"{STORAGE_DIR}.tmp"
        for dir_path in [backup_dir, temp_dir]:
            if os.path.exists(dir_path):
                shutil.rmtree(dir_path)
        logger.info("Index and storage cleared completely")

    def get_index(self) -> Optional[VectorStoreIndex]:
        """获取当前索引"""
        return self.index

    def is_index_available(self) -> bool:
        """检查索引是否可用"""
        return self.index is not None

    def get_corpus_size(self) -> int:
        """获取语料库大小"""
        if not self.index or not hasattr(self.index, "docstore"):
            return 0
        return len(self.index.docstore.docs)

    def __del__(self):
        """析构时停止自动持久化线程并确保数据持久化"""
        if hasattr(self, "_stop_persist_thread"):
            self._stop_persist_thread.set()

        if hasattr(self, "_persist_thread") and self._persist_thread.is_alive():
            self._persist_thread.join(timeout=5)

        # 退出前持久化脏数据
        if hasattr(self, "_dirty") and self._dirty and self.index is not None:
            try:
                self._persist_index()
                logger.info("Persisted index changes on shutdown")
            except Exception as e:
                logger.error(f"Failed to persist index on shutdown: {e}")
