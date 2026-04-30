import json
from typing import Callable, Dict, List, Optional

from llama_index.core import StorageContext, VectorStoreIndex
from llama_index.core.schema import Node

from src.config import settings
from src.core.vector_store_factory import VectorStoreFactory
from src.service.document_manager import document_manager
from src.utils.logger import logger


class IndexOperations:
    def __init__(self, storage_manager):
        self.storage_manager = storage_manager

    def insert_nodes(self, nodes: list[Node], progress_callback: Callable[[str, float, str], None] = None):
        logger.info(f"Starting index insertion for {len(nodes)} nodes")
        if not self.storage_manager.index:
            if progress_callback:
                progress_callback("indexing", 92.0, f"正在创建新索引，共 {len(nodes)} 个节点")
            logger.info("Creating new VectorStoreIndex from nodes")
            try:
                vector_store = VectorStoreFactory.get_vector_store()
                storage_context = StorageContext.from_defaults(vector_store=vector_store)
                batch_size = settings.rag_index_insert_batch_size
                total_nodes = len(nodes)
                if total_nodes > batch_size:
                    logger.info(f"Large dataset detected ({total_nodes} nodes), using batch processing")
                    self.storage_manager.index = VectorStoreIndex([], storage_context=storage_context, store_nodes_override=True)
                    for i in range(0, total_nodes, batch_size):
                        batch = nodes[i:i + batch_size]
                        batch_num = (i // batch_size) + 1
                        total_batches = (total_nodes + batch_size - 1) // batch_size
                        logger.info(f"Inserting batch {batch_num}/{total_batches}")
                        try:
                            self.storage_manager.index.insert_nodes(batch)
                            if progress_callback:
                                batch_progress = 92.0 + (3.0 * (i + batch_size) / total_nodes)
                                progress_callback("indexing", batch_progress, f"正在插入批次 {batch_num}/{total_batches}")
                        except Exception as batch_error:
                            logger.error(f"Failed to insert batch {batch_num}: {batch_error}")
                            if i + batch_size >= total_nodes and len(batch) == 1:
                                logger.warning(f"Skipping failed node at index {i}: {str(batch_error)[:200]}")
                            else:
                                raise
                else:
                    self.storage_manager.index = VectorStoreIndex(nodes, storage_context=storage_context, store_nodes_override=True)
                logger.info("New index created successfully")
            except Exception as e:
                logger.error(f"Failed to create index: {e}", exc_info=True)
                if progress_callback:
                    progress_callback("indexing", 92.0, f"创建索引失败：{str(e)}")
                raise
        else:
            if progress_callback:
                progress_callback("indexing", 92.0, f"正在插入 {len(nodes)} 个节点到现有索引")
            logger.info("Inserting nodes into existing index")
            self.storage_manager.index.insert_nodes(nodes)
            logger.info("Nodes inserted successfully")
        self.storage_manager._dirty = True
        if progress_callback:
            progress_callback("indexing", 95.0, "正在持久化索引到磁盘")
        logger.info("Starting index persistence")
        self.storage_manager._persist_index()
        self.storage_manager._dirty = False
        logger.info("Index persisted successfully")
        if progress_callback:
            progress_callback("indexing", 98.0, "索引构建完成")
        logger.info(f"Successfully inserted {len(nodes)} nodes into index")

    async def delete_document(self, file_name: str) -> bool:
        doc = await document_manager.get_document_by_name(file_name)
        if not doc:
            logger.warning(f"Document {file_name} not found in registry.")
            return False
        logger.info(f"Deleting document: {file_name} (hash: {doc['file_hash']}, status: {doc['status']})")

        try:
            await document_manager.delete_document(doc["file_hash"])
        except Exception as e:
            logger.error(f"Failed to delete document record: {e}")
            return False

        if not self.storage_manager.index:
            logger.warning("Index not initialized, document record deleted successfully.")
            return True

        try:
            if doc["status"] != "failed":
                for ref_id in doc["ref_doc_ids"]:
                    self.storage_manager.index.delete_ref_doc(ref_id, delete_from_docstore=True)
                self.storage_manager._persist_index()
                self.storage_manager._dirty = False

                remaining_docs = await document_manager.list_documents()
                if not remaining_docs:
                    self.storage_manager._clear_index()

            logger.info(f"Successfully deleted {file_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete document from index: {e}, but document record was deleted")
            return True

    def _parse_metadata_json_strings(self, metadata: dict) -> dict:
        if not metadata:
            return metadata
        parsed_metadata = metadata.copy()
        json_fields = ['topics', 'brain_regions']
        for field in json_fields:
            if field in parsed_metadata and isinstance(parsed_metadata[field], str):
                try:
                    parsed_value = json.loads(parsed_metadata[field])
                    if isinstance(parsed_value, list):
                        parsed_metadata[field] = parsed_value
                except (json.JSONDecodeError, TypeError):
                    logger.warning(f"Failed to parse {field} from metadata: {parsed_metadata[field]}")
                    parsed_metadata[field] = []
        return parsed_metadata

    def get_document_chunks(self, file_hash: str, page: int = 1, page_size: int = 20) -> dict:
        if not self.storage_manager.index:
            return {"total": 0, "chunks": [], "page": page, "page_size": page_size, "total_pages": 0}
        all_chunks = []

        # 主路径：从 Chroma 向量存储查询
        if hasattr(self.storage_manager.index, "_vector_store"):
            vector_store = self.storage_manager.index._vector_store
            try:
                if hasattr(vector_store, '_collection') and vector_store._collection:
                    collection = vector_store._collection
                    results = collection.get(where={"file_hash": file_hash}, include=["metadatas", "documents"])
                    if results and results['ids']:
                        for i, (doc_id, doc_text, metadata) in enumerate(zip(results['ids'], results['documents'], results['metadatas'])):
                            metadata = self._parse_metadata_json_strings(metadata)
                            start_idx = metadata.get('start_char_idx')
                            end_idx = metadata.get('end_char_idx')
                            if start_idx is None or end_idx is None:
                                start_idx = i * 1000
                                end_idx = start_idx + len(doc_text)
                            all_chunks.append({"id": doc_id, "content": doc_text, "metadata": metadata, "start_char_idx": start_idx, "end_char_idx": end_idx, "score": None})
            except Exception as e:
                logger.warning(f"Failed to get chunks from vector store, will try docstore: {e}")

        # 降级路径：Chroma 为空时从 docstore 查询（嵌入未计算时节点仅在 docstore 中）
        if not all_chunks and hasattr(self.storage_manager.index, "docstore"):
            docstore = self.storage_manager.index.docstore
            try:
                for node_id, node in docstore.docs.items():
                    node_meta = node.metadata if hasattr(node, 'metadata') else {}
                    if node_meta.get("file_hash") == file_hash:
                        metadata = self._parse_metadata_json_strings(dict(node_meta))
                        content = node.get_content() if hasattr(node, 'get_content') else node.text if hasattr(node, 'text') else ""
                        start_idx = metadata.get('start_char_idx', 0)
                        end_idx = metadata.get('end_char_idx', start_idx + len(content))
                        all_chunks.append({"id": node_id, "content": content, "metadata": metadata, "start_char_idx": start_idx, "end_char_idx": end_idx, "score": None})
                if all_chunks:
                    logger.info(f"Retrieved {len(all_chunks)} chunks from docstore (Chroma fallback)")
            except Exception as e:
                logger.error(f"Failed to get chunks from docstore: {e}")

        all_chunks.sort(key=lambda x: x["metadata"].get("page_label", "0"))
        total = len(all_chunks)
        total_pages = (total + page_size - 1) // page_size if total > 0 else 0
        page = max(1, min(page, total_pages)) if total_pages > 0 else 1
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        chunks = all_chunks[start_idx:end_idx]
        return {"total": total, "chunks": chunks, "page": page, "page_size": page_size, "total_pages": total_pages}

    def get_chunk_detail(self, chunk_id: str) -> Optional[dict]:
        if not self.storage_manager.index:
            return None

        # 主路径：从 Chroma 向量存储查询
        if hasattr(self.storage_manager.index, '_vector_store') and self.storage_manager.index._vector_store:
            vector_store = self.storage_manager.index._vector_store
            try:
                if hasattr(vector_store, '_collection') and vector_store._collection:
                    collection = vector_store._collection
                    results = collection.get(ids=[chunk_id], include=["metadatas", "documents"])
                    if results and results['ids']:
                        doc_id = results['ids'][0]
                        doc_text = results['documents'][0]
                        metadata = results['metadatas'][0]
                        metadata = self._parse_metadata_json_strings(metadata)
                        start_idx = metadata.get('start_char_idx')
                        end_idx = metadata.get('end_char_idx')
                        if start_idx is None or end_idx is None:
                            start_idx = 0
                            end_idx = len(doc_text)
                        return {"id": doc_id, "content": doc_text, "metadata": metadata, "start_char_idx": start_idx, "end_char_idx": end_idx, "relationships": {}}
            except Exception as e:
                logger.warning(f"Failed to get chunk detail from vector store, will try docstore: {e}")

        # 降级路径：从 docstore 查询
        if hasattr(self.storage_manager.index, "docstore"):
            docstore = self.storage_manager.index.docstore
            node = docstore.docs.get(chunk_id)
            if node:
                node_meta = node.metadata if hasattr(node, 'metadata') else {}
                metadata = self._parse_metadata_json_strings(dict(node_meta))
                content = node.get_content() if hasattr(node, 'get_content') else node.text if hasattr(node, 'text') else ""
                start_idx = metadata.get('start_char_idx', 0)
                end_idx = metadata.get('end_char_idx', start_idx + len(content))
                return {"id": chunk_id, "content": content, "metadata": metadata, "start_char_idx": start_idx, "end_char_idx": end_idx, "relationships": {}}

        return None

    @staticmethod
    def _safe_page_label(page_label: str) -> int:
        """安全转换 page_label 为 int，非数字值返回 0"""
        try:
            return int(page_label)
        except (ValueError, TypeError):
            return 0

    def get_all_chunks_by_file_hash(self, file_hash: str) -> List[dict]:
        """直接按 file_hash 读取文档的所有 chunks（非检索，不分页）"""
        if not self.storage_manager.index or not hasattr(self.storage_manager.index, "_vector_store"):
            return []
        vector_store = self.storage_manager.index._vector_store
        all_chunks = []
        try:
            if hasattr(vector_store, '_collection') and vector_store._collection:
                collection = vector_store._collection
                results = collection.get(where={"file_hash": file_hash}, include=["metadatas", "documents"])
                if results and results['ids']:
                    for i, (doc_id, doc_text, metadata) in enumerate(zip(results['ids'], results['documents'], results['metadatas'])):
                        metadata = self._parse_metadata_json_strings(metadata)
                        start_idx = metadata.get('start_char_idx')
                        end_idx = metadata.get('end_char_idx')
                        if start_idx is None or end_idx is None:
                            start_idx = i * 1000
                            end_idx = start_idx + len(doc_text)
                        all_chunks.append({"id": doc_id, "content": doc_text, "metadata": metadata, "start_char_idx": start_idx, "end_char_idx": end_idx, "score": None})
        except Exception as e:
            logger.error(f"Failed to get all chunks from vector store: {e}")
            return []
        # 按 page_label 排序
        all_chunks.sort(key=lambda x: self._safe_page_label(x["metadata"].get("page_label", "0")))
        return all_chunks

    def repair_vector_store(self) -> dict:
        """将 docstore 中有但 Chroma 中缺失的节点重新嵌入并写入向量存储。

        用于修复 docstore 与 Chroma 不同步的情况（如嵌入 API 临时故障、Chroma 数据丢失等）。

        Returns:
            dict: {"repaired": int, "skipped": int, "errors": int}
        """
        if not self.storage_manager.index:
            return {"repaired": 0, "skipped": 0, "errors": 0, "message": "索引未加载"}

        # 收集 Chroma 中已有的 node_id
        chroma_ids = set()
        if hasattr(self.storage_manager.index, "_vector_store"):
            vs = self.storage_manager.index._vector_store
            if hasattr(vs, '_collection') and vs._collection:
                try:
                    # 分批获取所有 ID，避免单次查询过大
                    all_ids = vs._collection.get(include=[])['ids']
                    chroma_ids = set(all_ids)
                except Exception as e:
                    logger.warning(f"无法读取 Chroma 现有 ID: {e}")

        # 收集 docstore 中缺失的节点
        missing_nodes = []
        if hasattr(self.storage_manager.index, "docstore"):
            for node_id, node in self.storage_manager.index.docstore.docs.items():
                if node_id not in chroma_ids:
                    missing_nodes.append(node)

        if not missing_nodes:
            return {"repaired": 0, "skipped": 0, "errors": 0, "message": "所有节点已同步，无需修复"}

        logger.info(f"发现 {len(missing_nodes)} 个节点在 Chroma 中缺失，开始修复...")
        repaired = 0
        errors = 0

        # 分批处理，与正常插入保持一致
        batch_size = settings.rag_index_insert_batch_size
        for i in range(0, len(missing_nodes), batch_size):
            batch = missing_nodes[i:i + batch_size]
            try:
                self.storage_manager.index.insert_nodes(batch)
                repaired += len(batch)
                logger.info(f"修复批次 {i // batch_size + 1}: {len(batch)} 个节点")
            except Exception as e:
                logger.error(f"修复批次失败: {e}")
                # 逐个尝试以隔离问题节点
                for node in batch:
                    try:
                        self.storage_manager.index.insert_nodes([node])
                        repaired += 1
                    except Exception as node_e:
                        logger.error(f"节点 {node.node_id} 修复失败: {node_e}")
                        errors += 1

        self.storage_manager._dirty = True
        self.storage_manager._persist_index()
        self.storage_manager._dirty = False

        result = {"repaired": repaired, "skipped": len(missing_nodes) - repaired - errors, "errors": errors}
        logger.info(f"向量存储修复完成: {result}")
        return result
