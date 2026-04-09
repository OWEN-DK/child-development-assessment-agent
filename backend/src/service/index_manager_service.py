import os
import threading
import time
import shutil
from typing import Optional, Callable, List, Dict
from llama_index.core import (
    VectorStoreIndex,
    StorageContext,
    load_index_from_storage,
    Settings,
)
from llama_index.core.schema import Node
from src.config import settings
from src.utils.logger import logger
from src.service.document_manager import document_manager
from src.core.vector_store_factory import VectorStoreFactory

STORAGE_DIR = settings.rag_storage_dir


from src.core.interfaces import IIndexManager
from src.core.event_bus import event_bus, IndexUpdateEvent
import uuid


class IndexManagerService(IIndexManager):
    """索引管理服务，负责索引的初始化、加载、更新、持久化"""

    def __init__(self):
        self.index: Optional[VectorStoreIndex] = None
        self.index_id = str(uuid.uuid4())
        self.index_version = self.index_id

        # 计算配置指纹
        import hashlib
        import json

        config_str = json.dumps(settings.rag_config, sort_keys=True)
        self.config_fingerprint = hashlib.md5(config_str.encode()).hexdigest()

        self._dirty = False  # 索引是否有未持久化的更改
        self._persist_thread = None
        self._stop_persist_thread = threading.Event()
        self._initialize_index()
        self._start_auto_persist()

    def _initialize_index(self):
        """从存储中初始化向量索引，带有重试机制和备份恢复"""
        index_dir = os.path.join(STORAGE_DIR, "index")
        if not os.path.exists(index_dir):
            os.makedirs(index_dir, exist_ok=True)

        max_retries = 3
        retry_delay = 1  # 秒

        try:
            # 使用向量存储工厂获取向量存储实例
            vector_store = VectorStoreFactory.get_vector_store()
            logger.info(f"Using vector store type: {settings.vector_store_type}")
        except Exception as e:
            logger.error(f"Failed to initialize vector store: {e}")
            raise

        for attempt in range(max_retries):
            try:
                if os.path.exists(os.path.join(index_dir, "docstore.json")):
                    logger.info(
                        f"Loading index from storage (attempt {attempt + 1}/{max_retries})..."
                    )
                    storage_context = StorageContext.from_defaults(
                        persist_dir=index_dir, vector_store=vector_store
                    )
                    self.index = load_index_from_storage(storage_context)
                    logger.info("Index loaded successfully.")
                    return
                else:
                    logger.warning("No existing index found (missing docstore.json). Waiting for file uploads.")
                    # 尝试从向量数据库加载已存在的集合
                    if settings.vector_store_type == "chroma" and "collection_name" in settings.vector_store_config:
                        logger.info("Attempting to load from Chroma vector store directly")
                        try:
                            storage_context = StorageContext.from_defaults(
                                vector_store=vector_store
                            )
                            self.index = VectorStoreIndex.from_vector_store(
                                vector_store, storage_context=storage_context
                            )
                            logger.info("Successfully created index from existing vector store")
                            return
                        except Exception as vc_e:
                            logger.warning(f"Failed to load from vector store: {vc_e}")
                    
                    self.index = None
                    return
            except Exception as e:
                logger.error(
                    f"Failed to load index from storage (attempt {attempt + 1}/{max_retries}): {e}"
                )

                # 最后一次尝试失败，尝试从备份恢复
                if attempt == max_retries - 1:
                    backup_dir = f"{index_dir}.bak"
                    if os.path.exists(backup_dir) and os.path.exists(os.path.join(backup_dir, "docstore.json")):
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
                    if os.path.exists(index_dir):
                        corrupted_dir = f"{index_dir}.corrupted.{int(time.time())}"
                        try:
                            os.rename(index_dir, corrupted_dir)
                            logger.info(
                                f"Corrupted index directory moved to: {corrupted_dir}"
                            )
                        except Exception as rename_error:
                            logger.error(
                                f"Failed to move corrupted directory: {rename_error}"
                            )
                            # 如果重命名失败，直接删除
                            shutil.rmtree(index_dir)

                    os.makedirs(index_dir, exist_ok=True)
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
            try:
                # 创建新索引，使用配置的向量存储
                vector_store = VectorStoreFactory.get_vector_store()
                storage_context = StorageContext.from_defaults(
                    vector_store=vector_store
                )
                
                # 分批处理以避免单次 API 调用过多导致超时
                # 对于大量节点，使用分批插入策略
                batch_size = 200  # 每批处理 200 个节点
                total_nodes = len(nodes)
                
                if total_nodes > batch_size:
                    logger.info(f"Large dataset detected ({total_nodes} nodes), using batch processing")
                    # 先创建空索引
                    self.index = VectorStoreIndex([], storage_context=storage_context, store_nodes_override=True)
                    
                    # 分批插入
                    for i in range(0, total_nodes, batch_size):
                        batch = nodes[i:i + batch_size]
                        batch_num = (i // batch_size) + 1
                        total_batches = (total_nodes + batch_size - 1) // batch_size
                        
                        logger.info(f"Inserting batch {batch_num}/{total_batches} (nodes {i}-{min(i + batch_size, total_nodes)})")
                        
                        try:
                            # 使用 insert_nodes 批量插入
                            self.index.insert_nodes(batch)
                            
                            # 更新进度
                            if progress_callback:
                                batch_progress = 92.0 + (3.0 * (i + batch_size) / total_nodes)
                                progress_callback(
                                    "indexing", 
                                    batch_progress, 
                                    f"正在插入批次 {batch_num}/{total_batches}"
                                )
                        except Exception as batch_error:
                            logger.error(f"Failed to insert batch {batch_num}: {batch_error}")
                            # 如果是最后一个节点失败，记录警告但继续
                            if i + batch_size >= total_nodes and len(batch) == 1:
                                logger.warning(f"Skipping failed node at index {i}: {str(batch_error)[:200]}")
                            else:
                                raise
                else:
                    # 小数据集直接创建
                    self.index = VectorStoreIndex(nodes, storage_context=storage_context, store_nodes_override=True)
                
                logger.info("New index created successfully")
                
            except Exception as e:
                logger.error(f"Failed to create index: {e}", exc_info=True)
                if progress_callback:
                    progress_callback("indexing", 92.0, f"创建索引失败：{str(e)}")
                raise
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
            index_dir = os.path.join(STORAGE_DIR, "index")
            # 创建临时目录进行原子写入
            temp_dir = f"{index_dir}.tmp"
            backup_dir = f"{index_dir}.bak"

            try:
                # 先写入到临时目录
                if os.path.exists(temp_dir):
                    shutil.rmtree(temp_dir)
                os.makedirs(temp_dir, exist_ok=True)

                # 关键修复：先手动持久化 docstore 到 JSON 文件
                # 这是因为 LlamaIndex 的 storage_context.persist() 在使用 Chroma 向量存储时
                # 可能不会正确保存 docstore 到 docstore.json 文件
                if hasattr(self.index, 'docstore') and self.index.docstore:
                    import json
                    docstore_path = os.path.join(temp_dir, "docstore.json")
                    docs = {}
                    for doc_id, node in self.index.docstore.docs.items():
                        docs[doc_id] = {
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
                    docstore_data = {"docs": docs}
                    with open(docstore_path, 'w', encoding='utf-8') as f:
                        json.dump(docstore_data, f, ensure_ascii=False, indent=2)
                    logger.info(f"Manually persisted {len(docs)} documents to docstore.json")

                # 然后使用 storage_context 持久化其他索引数据
                self.index.storage_context.persist(persist_dir=temp_dir)

                # 备份现有目录
                if os.path.exists(index_dir):
                    if os.path.exists(backup_dir):
                        shutil.rmtree(backup_dir)
                    os.rename(index_dir, backup_dir)

                # 替换为新目录
                os.rename(temp_dir, index_dir)

                # 清理备份
                if os.path.exists(backup_dir):
                    shutil.rmtree(backup_dir)

                # 发布索引更新事件
                event_bus.publish(IndexUpdateEvent(self.index_id))
                logger.debug(
                    "Index persisted to disk atomically, update event published"
                )
            except Exception as e:
                logger.error(f"Failed to persist index: {e}")
                # 回滚
                if os.path.exists(backup_dir) and not os.path.exists(index_dir):
                    try:
                        os.rename(backup_dir, index_dir)
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
        
        index_dir = os.path.join(STORAGE_DIR, "index")
        # 删除存储目录
        if os.path.exists(index_dir):
            shutil.rmtree(index_dir)
            os.makedirs(index_dir, exist_ok=True)
        # 清理备份文件
        backup_dir = f"{index_dir}.bak"
        temp_dir = f"{index_dir}.tmp"
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
        if not self.index:
            return 0
        
        # 优先从向量存储获取（适用于 Chroma）
        if hasattr(self.index, '_vector_store') and self.index._vector_store:
            vector_store = self.index._vector_store
            if hasattr(vector_store, '_collection') and vector_store._collection:
                try:
                    return vector_store._collection.count()
                except:
                    pass
        
        # 回退到 docstore 方式
        if hasattr(self.index, 'docstore'):
            return len(self.index.docstore.docs)
        
        return 0
    
    def _parse_metadata_json_strings(self, metadata: dict) -> dict:
        """解析 metadata 中的 JSON 字符串字段为数组
        
        由于 metadata extraction 失败时会将列表字段转换为 JSON 字符串存储，
        在返回给客户端之前需要解析回数组格式。
        
        Args:
            metadata: 原始元数据字典
            
        Returns:
            解析后的元数据字典
        """
        import json
        
        if not metadata:
            return metadata
            
        # 创建新字典避免修改原始数据
        parsed_metadata = metadata.copy()
        
        # 需要解析的字段列表
        json_fields = ['topics', 'brain_regions']
        
        for field in json_fields:
            if field in parsed_metadata and isinstance(parsed_metadata[field], str):
                try:
                    parsed_value = json.loads(parsed_metadata[field])
                    # 确保解析结果是列表
                    if isinstance(parsed_value, list):
                        parsed_metadata[field] = parsed_value
                except (json.JSONDecodeError, TypeError):
                    # 解析失败则保留原值或设置为空列表
                    logger.warning(f"Failed to parse {field} from metadata: {parsed_metadata[field]}")
                    parsed_metadata[field] = []
        
        return parsed_metadata
    
    def get_document_chunks(self, file_hash: str, page: int = 1, page_size: int = 20) -> dict:
        """获取指定文档的分块列表（支持分页）
        
        Args:
            file_hash: 文档哈希值
            page: 页码（从 1 开始）
            page_size: 每页数量
            
        Returns:
            包含分页信息的字典：{total, chunks, page, page_size, total_pages}
        """
        if not self.index or not hasattr(self.index, "_vector_store"):
            return {"total": 0, "chunks": [], "page": page, "page_size": page_size, "total_pages": 0}
        
        # 从向量存储中获取数据（适用于 Chroma 等向量库）
        vector_store = self.index._vector_store
        all_chunks = []
        
        try:
            # 检查是否有 Chroma 集合
            if hasattr(vector_store, '_collection') and vector_store._collection:
                collection = vector_store._collection
                
                # 查询指定 file_hash 的所有文档
                results = collection.get(
                    where={"file_hash": file_hash},
                    include=["metadatas", "documents"]
                )
                
                if results and results['ids']:
                    for i, (doc_id, doc_text, metadata) in enumerate(zip(
                        results['ids'], 
                        results['documents'], 
                        results['metadatas']
                    )):
                        # 解析 JSON 字符串字段为数组
                        metadata = self._parse_metadata_json_strings(metadata)
                        # 如果 metadata 中没有 start_char_idx 和 end_char_idx，使用文本长度计算
                        start_idx = metadata.get('start_char_idx')
                        end_idx = metadata.get('end_char_idx')
                        if start_idx is None or end_idx is None:
                            # 使用枚举索引作为替代，或者基于文本长度计算
                            start_idx = i * 1000  # 估算值，每个 chunk 假设 1000 字符
                            end_idx = start_idx + len(doc_text)
                        
                        all_chunks.append({
                            "id": doc_id,
                            "content": doc_text,
                            "metadata": metadata,
                            "start_char_idx": start_idx,
                            "end_char_idx": end_idx,
                            "score": None
                        })
            else:
                # 回退到 docstore 方式（兼容旧版本）
                if hasattr(self.index, 'docstore'):
                    docstore = self.index.docstore
                    for doc_id, node in docstore.docs.items():
                        if node.metadata.get("file_hash") == file_hash:
                            # 解析 JSON 字符串字段为数组
                            metadata = self._parse_metadata_json_strings(node.metadata)
                            all_chunks.append({
                                "id": doc_id,
                                "content": node.text,
                                "metadata": metadata,
                                "start_char_idx": node.start_char_idx,
                                "end_char_idx": node.end_char_idx,
                                "score": None
                            })
        except Exception as e:
            logger.error(f"Failed to get chunks from vector store: {e}")
            # 回退到 docstore 方式
            if hasattr(self.index, 'docstore'):
                docstore = self.index.docstore
                for doc_id, node in docstore.docs.items():
                    if node.metadata.get("file_hash") == file_hash:
                        # 解析 JSON 字符串字段为数组
                        metadata = self._parse_metadata_json_strings(node.metadata)
                        all_chunks.append({
                            "id": doc_id,
                            "content": node.text,
                            "metadata": metadata,
                            "start_char_idx": node.start_char_idx,
                            "end_char_idx": node.end_char_idx,
                            "score": None
                        })
        
        # 按页码排序
        all_chunks.sort(key=lambda x: x["metadata"].get("page_label", "0"))
        
        # 分页
        total = len(all_chunks)
        total_pages = (total + page_size - 1) // page_size if total > 0 else 0
        
        # 确保页码在有效范围内
        page = max(1, min(page, total_pages)) if total_pages > 0 else 1
        
        # 计算分页切片
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        chunks = all_chunks[start_idx:end_idx]
        
        return {
            "total": total,
            "chunks": chunks,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages
        }
    
    def get_chunk_detail(self, chunk_id: str) -> Optional[dict]:
        """获取指定分块的详细信息"""
        if not self.index:
            return None
        
        # 优先从向量存储中获取（适用于 Chroma）
        if hasattr(self.index, '_vector_store') and self.index._vector_store:
            vector_store = self.index._vector_store
            try:
                if hasattr(vector_store, '_collection') and vector_store._collection:
                    collection = vector_store._collection
                    
                    # 根据 chunk_id 查询
                    results = collection.get(
                        ids=[chunk_id],
                        include=["metadatas", "documents"]
                    )
                    
                    if results and results['ids']:
                        doc_id = results['ids'][0]
                        doc_text = results['documents'][0]
                        metadata = results['metadatas'][0]
                        # 解析 JSON 字符串字段为数组
                        metadata = self._parse_metadata_json_strings(metadata)
                        
                        # 如果 metadata 中没有 start_char_idx 和 end_char_idx，使用文本长度计算
                        start_idx = metadata.get('start_char_idx')
                        end_idx = metadata.get('end_char_idx')
                        if start_idx is None or end_idx is None:
                            start_idx = 0  # 无法确定起始位置时设为 0
                            end_idx = len(doc_text)
                        
                        return {
                            "id": doc_id,
                            "content": doc_text,
                            "metadata": metadata,
                            "start_char_idx": start_idx,
                            "end_char_idx": end_idx,
                            "relationships": {}
                        }
            except Exception as e:
                logger.error(f"Failed to get chunk detail from vector store: {e}")
        
        # 回退到 docstore 方式（兼容旧版本）
        if hasattr(self.index, 'docstore'):
            docstore = self.index.docstore
            if chunk_id not in docstore.docs:
                return None
            
            node = docstore.docs[chunk_id]
            # 解析 JSON 字符串字段为数组
            metadata = self._parse_metadata_json_strings(node.metadata)
            return {
                "id": chunk_id,
                "content": node.text,
                "metadata": metadata,
                "start_char_idx": node.start_char_idx,
                "end_char_idx": node.end_char_idx,
                "relationships": node.relationships
            }
        
        return None

    def __del__(self):
        """析构时停止自动持久化线程并确保数据持久化"""
        if hasattr(self, "_stop_persist_thread"):
            self._stop_persist_thread.set()

        if hasattr(self, "_persist_thread") and self._persist_thread is not None and self._persist_thread.is_alive():
            self._persist_thread.join(timeout=5)

        # 退出前持久化脏数据
        if hasattr(self, "_dirty") and self._dirty and self.index is not None:
            try:
                self._persist_index()
                logger.info("Persisted index changes on shutdown")
            except Exception as e:
                logger.error(f"Failed to persist index on shutdown: {e}")
