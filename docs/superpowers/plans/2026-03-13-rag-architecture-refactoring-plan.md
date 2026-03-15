# RAG 架构重构实施计划

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 解决RAG模块的三个架构设计问题，提升代码可维护性和扩展性
**Architecture:** 
1. 将庞大的RagService拆分为多个单一职责的服务类（检索服务、索引管理服务、文档导入服务、缓存服务）
2. 提取混合检索分数融合逻辑为独立的工具类/方法，统一两处检索逻辑
3. 提取元数据提取的公共方法，消除重复代码
**Tech Stack:** Python 3.13, LangGraph, LlamaIndex, Pydantic

---

## 架构重构方案

### 拆分后的服务边界
| 服务类 | 职责 | 文件路径 |
|--------|------|----------|
| `RetrievalService` | 处理所有检索相关逻辑（混合检索、查询重写、同义词扩展、结果过滤） | `backend/src/service/retrieval_service.py` |
| `IndexManagerService` | 索引的初始化、加载、持久化、更新、删除 | `backend/src/service/index_manager_service.py` |
| `DocumentIngestionService` | 文档解析、分块、元数据提取、索引插入 | `backend/src/service/document_ingestion_service.py` |
| `CacheService` | 检索结果的缓存管理 | `backend/src/service/cache_service.py` |
| `HybridRetrievalMerger` | 混合检索结果的分数融合逻辑（独立工具类） | `backend/src/core/hybrid_retrieval.py` |
| `MetadataProcessor` | 元数据提取的公共处理逻辑（独立工具类） | `backend/src/core/metadata_processor.py` |

---

## Task 1: 创建混合检索工具类，统一分数融合逻辑

**Files:**
- Create: `backend/src/core/hybrid_retrieval.py`
- Modify: `backend/src/service/rag_service.py` (后续将删除相关逻辑)
- Test: `backend/tests/test_hybrid_retrieval.py`

- [ ] **Step 1: 创建HybridRetrievalMerger类**

```python
from typing import List, Dict, Any, Tuple
from llama_index.core.schema import NodeWithScore
from src.config.settings import settings
from src.utils.logger import logger

class HybridRetrievalMerger:
    """混合检索结果融合器，统一处理BM25和向量检索结果的分数融合"""
    
    @staticmethod
    def merge_results(
        bm25_nodes: List[NodeWithScore],
        vector_nodes: List[NodeWithScore],
        bm25_weight: float = 0.5,
        vector_weight: float = 0.5,
        merge_mode: str = "OR",
        limit: int = 10,
        normalize_scores: bool = True
    ) -> List[NodeWithScore]:
        """
        合并BM25和向量检索结果
        Args:
            bm25_nodes: BM25检索结果
            vector_nodes: 向量检索结果
            bm25_weight: BM25分数权重
            vector_weight: 向量分数权重
            merge_mode: 合并模式 ("OR" - 并集, "AND" - 交集)
            limit: 返回结果数量限制
            normalize_scores: 是否归一化分数到0-1范围
        Returns:
            合并排序后的结果
        """
        if not bm25_nodes and not vector_nodes:
            return []
        
        # 归一化分数
        if normalize_scores:
            bm25_nodes = HybridRetrievalMerger._normalize_scores(bm25_nodes)
            vector_nodes = HybridRetrievalMerger._normalize_scores(vector_nodes)
        
        node_map: Dict[str, NodeWithScore] = {}
        
        # 处理BM25结果
        for node in bm25_nodes:
            node_id = node.node.node_id
            node.score = (node.score or 0.0) * bm25_weight
            node_map[node_id] = node
        
        # 处理向量结果
        for node in vector_nodes:
            node_id = node.node.node_id
            vector_score = (node.score or 0.0) * vector_weight
            
            if node_id in node_map:
                # 合并分数
                existing_node = node_map[node_id]
                existing_node.score = (existing_node.score or 0.0) + vector_score
            else:
                if merge_mode == "OR":
                    # 并集模式下添加仅在向量结果中的节点
                    node.score = vector_score
                    node_map[node_id] = node
        
        # 转换为列表并排序
        merged_nodes = sorted(
            node_map.values(),
            key=lambda x: x.score or 0.0,
            reverse=True
        )[:limit]
        
        logger.debug(f"Merged {len(bm25_nodes)} BM25 nodes and {len(vector_nodes)} vector nodes into {len(merged_nodes)} results")
        return merged_nodes
    
    @staticmethod
    def _normalize_scores(nodes: List[NodeWithScore]) -> List[NodeWithScore]:
        """将分数归一化到0-1范围"""
        if not nodes:
            return nodes
        
        scores = [node.score or 0.0 for node in nodes]
        max_score = max(scores)
        min_score = min(scores)
        
        if max_score == min_score:
            # 所有分数相同，归一化为1.0
            for node in nodes:
                node.score = 1.0
            return nodes
        
        # 线性归一化
        for node in nodes:
            node.score = ((node.score or 0.0) - min_score) / (max_score - min_score)
        
        return nodes
    
    @staticmethod
    def merge_for_search(
        bm25_nodes: List[NodeWithScore],
        vector_nodes: List[NodeWithScore],
        bm25_weight: float = 0.7,
        vector_weight: float = 0.3,
        no_match_vector_penalty: float = 0.3,
        limit: int = 20
    ) -> List[NodeWithScore]:
        """
        专为搜索页面设计的合并逻辑，包含关键词匹配惩罚机制
        """
        if not bm25_nodes and not vector_nodes:
            return []
        
        # 归一化BM25分数
        max_bm25 = 0.0
        if bm25_nodes:
            max_bm25 = max(n.score for n in bm25_nodes) if bm25_nodes[0].score else 1.0
            if max_bm25 > 0:
                for n in bm25_nodes:
                    n.score = (n.score or 0.0) / max_bm25
        
        # 向量检索惩罚：如果没有BM25匹配，降低向量结果权重
        vector_penalty = 1.0 if max_bm25 > 0 else no_match_vector_penalty
        
        node_map: Dict[str, NodeWithScore] = {}
        
        # 处理BM25结果
        for node in bm25_nodes:
            node_id = node.node.node_id
            node.score = (node.score or 0.0) * bm25_weight
            node_map[node_id] = node
        
        # 处理向量结果
        for node in vector_nodes:
            node_id = node.node.node_id
            vector_score = (node.score or 0.0) * vector_weight * vector_penalty
            
            if node_id in node_map:
                node_map[node_id].score = (node_map[node_id].score or 0.0) + vector_score
            else:
                node.score = vector_score
                node_map[node_id] = node
        
        # 排序并返回
        merged_nodes = sorted(
            node_map.values(),
            key=lambda x: x.score or 0.0,
            reverse=True
        )[:limit]
        
        return merged_nodes
```

- [ ] **Step 2: 创建测试文件验证融合逻辑**

```python
import pytest
from llama_index.core.schema import NodeWithScore, TextNode
from src.core.hybrid_retrieval import HybridRetrievalMerger

def test_merge_basic():
    """测试基础合并功能"""
    # 创建测试节点
    node1 = NodeWithScore(node=TextNode(text="test1", id_="1"), score=0.8)
    node2 = NodeWithScore(node=TextNode(text="test2", id_="2"), score=0.6)
    node3 = NodeWithScore(node=TextNode(text="test3", id_="3"), score=0.9)
    node4 = NodeWithScore(node=TextNode(text="test4", id_="4"), score=0.7)
    
    bm25_nodes = [node1, node2]
    vector_nodes = [node2, node3, node4]
    
    # 合并结果
    merged = HybridRetrievalMerger.merge_results(
        bm25_nodes,
        vector_nodes,
        bm25_weight=0.5,
        vector_weight=0.5,
        limit=10
    )
    
    # 验证结果
    assert len(merged) == 4
    # node2同时出现在两个结果中，分数应该是0.6*0.5 + 0.9*0.5 = 0.75
    # node3: 0.9*0.5 = 0.45
    # node4: 0.7*0.5 = 0.35
    # node1: 0.8*0.5 = 0.4
    # 排序应该是: node2 (0.75), node1 (0.4), node3 (0.45？不对，重新计算)
    # 正确分数:
    # node2: 0.6*0.5 + 0.9*0.5 = 0.3 + 0.45 = 0.75
    # node3: 0.9*0.5 = 0.45
    # node1: 0.8*0.5 = 0.4
    # node4: 0.7*0.5 = 0.35
    assert merged[0].node.node_id == "2"
    assert merged[1].node.node_id == "3"
    assert merged[2].node.node_id == "1"
    assert merged[3].node.node_id == "4"

def test_normalize_scores():
    """测试分数归一化功能"""
    nodes = [
        NodeWithScore(node=TextNode(id_="1"), score=2.0),
        NodeWithScore(node=TextNode(id_="2"), score=4.0),
        NodeWithScore(node=TextNode(id_="3"), score=6.0),
    ]
    
    normalized = HybridRetrievalMerger._normalize_scores(nodes)
    
    assert normalized[0].score == 0.0
    assert normalized[1].score == 0.5
    assert normalized[2].score == 1.0

def test_merge_for_search_with_penalty():
    """测试搜索场景下的合并逻辑（带惩罚机制）"""
    node1 = NodeWithScore(node=TextNode(text="football", id_="1"), score=10.0)  # BM25高分
    node2 = NodeWithScore(node=TextNode(text="block", id_="2"), score=0.0)  # BM25无匹配
    
    bm25_nodes = [node1]
    vector_nodes = [
        NodeWithScore(node=TextNode(text="football", id_="1"), score=0.9),
        NodeWithScore(node=TextNode(text="block", id_="2"), score=0.8),
    ]
    
    merged = HybridRetrievalMerger.merge_for_search(
        bm25_nodes,
        vector_nodes,
        bm25_weight=0.7,
        vector_weight=0.3,
        no_match_vector_penalty=0.3
    )
    
    # node1分数: 1.0 * 0.7 + 0.9 * 0.3 = 0.7 + 0.27 = 0.97
    # node2分数: 0.0 * 0.7 + 0.8 * 0.3 * 0.3 = 0.072
    assert len(merged) == 2
    assert merged[0].node.node_id == "1"
    assert merged[0].score == pytest.approx(0.97)
    assert merged[1].score == pytest.approx(0.072)
```

- [ ] **Step 3: 运行测试验证功能**
```bash
cd backend
uv run pytest tests/test_hybrid_retrieval.py -v
```
Expected: All tests pass

---

## Task 2: 创建元数据处理工具类，消除重复代码

**Files:**
- Create: `backend/src/core/metadata_processor.py`
- Modify: `backend/src/service/rag_service.py` (后续将删除相关逻辑)
- Test: `backend/tests/test_metadata_processor.py`

- [ ] **Step 1: 创建MetadataProcessor类**

```python
import asyncio
from typing import List
from llama_index.core.schema import Node, Document
from llama_index.core.node_parser import SentenceSplitter
from src.core.metadata_extractor import MetadataExtractor
from src.config.settings import settings
from src.utils.logger import logger

class MetadataProcessor:
    """元数据处理工具类，统一处理节点的元数据提取"""
    
    def __init__(self, concurrency: int = None):
        self.concurrency = concurrency or settings.rag_metadata_extraction_concurrency
        self.semaphore = asyncio.Semaphore(self.concurrency)
    
    async def process_nodes(
        self,
        nodes: List[Node],
        file_hash: str,
        progress_callback=None,
        total_chunks: int = None
    ) -> List[Node]:
        """
        批量处理节点，提取元数据
        Args:
            nodes: 待处理的节点列表
            file_hash: 文档的哈希值，用于关联
            progress_callback: 进度回调函数
            total_chunks: 总块数，用于进度计算
        Returns:
            处理后的节点列表
        """
        if total_chunks is None:
            total_chunks = len(nodes)
        
        processed_count = 0
        extraction_tasks = []
        
        async def process_single_node(node: Node) -> Node:
            nonlocal processed_count
            async with self.semaphore:
                # 提取元数据
                extracted_meta = await MetadataExtractor.extract(node.get_content())
                # 合并元数据
                node.metadata.update(extracted_meta.model_dump())
                node.metadata["content"] = node.get_content()
                node.metadata["file_hash"] = file_hash
                
                processed_count += 1
                if progress_callback and (processed_count % 5 == 0 or processed_count == total_chunks):
                    progress = (processed_count / total_chunks) * 100
                    progress_callback("metadata_extraction", progress, f"处理中: {processed_count}/{total_chunks}")
                
                return node
        
        # 创建所有处理任务
        for node in nodes:
            extraction_tasks.append(process_single_node(node))
        
        # 并发执行
        processed_nodes = await asyncio.gather(*extraction_tasks)
        logger.info(f"Completed metadata extraction for {len(processed_nodes)} nodes")
        
        return processed_nodes
    
    @staticmethod
    def split_chapters_into_chunks(
        documents: List[Document],
        chunk_target_size: int = 800,
        file_hash: str = None
    ) -> List[Node]:
        """
        将章节级文档拆分为更小的块（适用于EPUB和带书签的PDF）
        Args:
            documents: 章节级文档列表
            chunk_target_size: 目标块大小（字符数）
            file_hash: 文档哈希值，用于设置源关联
        Returns:
            拆分后的节点列表
        """
        all_nodes = []
        
        for doc in documents:
            chapter_title = doc.metadata.get("chapter_title", "")
            page_label = doc.metadata.get("page_label", "")
            
            # 按段落分割
            paragraphs = [p.strip() for p in doc.text.split("\n\n") if p.strip()]
            
            current_chunk = ""
            for para in paragraphs:
                if len(current_chunk) + len(para) < chunk_target_size:
                    current_chunk += para + "\n\n"
                else:
                    if current_chunk:
                        # 创建新块
                        chunk_doc = Document(
                            text=current_chunk.strip(),
                            metadata=doc.metadata.copy()
                        )
                        if file_hash:
                            from llama_index.core.schema import NodeRelationship, RelatedNodeInfo
                            chunk_doc.relationships[NodeRelationship.SOURCE] = RelatedNodeInfo(
                                node_id=file_hash
                            )
                        all_nodes.append(chunk_doc)
                    current_chunk = para + "\n\n"
            
            # 添加最后一个块
            if current_chunk:
                chunk_doc = Document(
                    text=current_chunk.strip(),
                    metadata=doc.metadata.copy()
                )
                if file_hash:
                    from llama_index.core.schema import NodeRelationship, RelatedNodeInfo
                    chunk_doc.relationships[NodeRelationship.SOURCE] = RelatedNodeInfo(
                        node_id=file_hash
                    )
                all_nodes.append(chunk_doc)
        
        logger.info(f"Split {len(documents)} chapters into {len(all_nodes)} chunks")
        return all_nodes
    
    @staticmethod
    def split_pages_into_chunks(
        documents: List[Document],
        chunk_size: int = 1536,
        chunk_overlap: int = 20,
        file_hash: str = None
    ) -> List[Node]:
        """
        将页级文档拆分为更小的块（适用于普通PDF）
        Args:
            documents: 页级文档列表
            chunk_size: 块大小
            chunk_overlap: 块重叠大小
            file_hash: 文档哈希值，用于设置源关联
        Returns:
            拆分后的节点列表
        """
        splitter = SentenceSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        all_chunks = []
        
        for doc in documents:
            nodes = splitter.get_nodes_from_documents([doc])
            if file_hash:
                from llama_index.core.schema import NodeRelationship, RelatedNodeInfo
                for node in nodes:
                    node.relationships[NodeRelationship.SOURCE] = RelatedNodeInfo(
                        node_id=file_hash
                    )
            all_chunks.extend(nodes)
        
        logger.info(f"Split {len(documents)} pages into {len(all_chunks)} chunks")
        return all_chunks
```

- [ ] **Step 2: 创建测试文件**

```python
import pytest
import asyncio
from llama_index.core.schema import Document
from src.core.metadata_processor import MetadataProcessor

def test_split_chapters_into_chunks():
    """测试章节拆分功能"""
    doc = Document(
        text="段落1\n\n段落2\n\n段落3\n\n段落4\n\n段落5",
        metadata={"chapter_title": "测试章节", "page_label": "1-5"}
    )
    
    chunks = MetadataProcessor.split_chapters_into_chunks(
        [doc],
        chunk_target_size=20  # 小目标大小，测试拆分效果
    )
    
    assert len(chunks) > 1
    for chunk in chunks:
        assert "chapter_title" in chunk.metadata
        assert chunk.metadata["chapter_title"] == "测试章节"

def test_split_pages_into_chunks():
    """测试页面拆分功能"""
    doc = Document(
        text="这是一个很长的文本内容。" * 100,
        metadata={"page_label": "1"}
    )
    
    chunks = MetadataProcessor.split_pages_into_chunks(
        [doc],
        chunk_size=100,
        chunk_overlap=20
    )
    
    assert len(chunks) > 1
    for chunk in chunks:
        assert len(chunk.text) <= 120  # 块大小+重叠

@pytest.mark.asyncio
async def test_process_nodes():
    """测试元数据处理功能（需要DashScope API Key）"""
    # 创建测试节点
    doc = Document(
        text="足球运动可以锻炼儿童的协调性和平衡能力，促进前庭觉发育。",
        metadata={"page_label": "1"}
    )
    
    processor = MetadataProcessor(concurrency=1)
    processed_nodes = await processor.process_nodes([doc], file_hash="test_hash")
    
    assert len(processed_nodes) == 1
    node = processed_nodes[0]
    assert "topics" in node.metadata
    assert "brain_regions" in node.metadata
    assert node.metadata["file_hash"] == "test_hash"
```

- [ ] **Step 3: 运行测试**
```bash
cd backend
uv run pytest tests/test_metadata_processor.py -v
```
Expected: All tests pass

---

## Task 3: 拆分RagService为多个单一职责服务

### Task 3.1: 创建索引管理服务

**Files:**
- Create: `backend/src/service/index_manager_service.py`
- Modify: `backend/src/service/rag_service.py` (继承/复用逻辑)

- [ ] **Step 1: 实现IndexManagerService**

```python
import os
from typing import Optional
from llama_index.core import VectorStoreIndex, StorageContext, load_index_from_storage, Settings
from llama_index.core.schema import Node
from src.config.settings import settings
from src.utils.logger import logger
from src.service.document_manager import document_manager

STORAGE_DIR = settings.rag_storage_dir

class IndexManagerService:
    """索引管理服务，负责索引的初始化、加载、更新、持久化"""
    
    def __init__(self):
        self.index: Optional[VectorStoreIndex] = None
        self._initialize_index()
    
    def _initialize_index(self):
        """从存储中初始化向量索引"""
        if not os.path.exists(STORAGE_DIR):
            os.makedirs(STORAGE_DIR)
        
        try:
            if os.path.exists(os.path.join(STORAGE_DIR, "docstore.json")):
                logger.info("Loading index from storage...")
                storage_context = StorageContext.from_defaults(persist_dir=STORAGE_DIR)
                self.index = load_index_from_storage(storage_context)
                logger.info("Index loaded successfully.")
            else:
                logger.warning("No existing index found. Waiting for file uploads.")
                self.index = None
        except Exception as e:
            logger.error(f"Failed to load index from storage: {e}")
            self.index = None
    
    def insert_nodes(self, nodes: list[Node]):
        """插入节点到索引"""
        if not self.index:
            # 创建新索引
            self.index = VectorStoreIndex(nodes)
        else:
            # 增量插入
            self.index.insert_nodes(nodes)
        
        # 持久化
        self._persist_index()
        logger.info(f"Inserted {len(nodes)} nodes into index")
    
    def delete_document(self, file_name: str) -> bool:
        """根据文件名删除文档"""
        if not self.index:
            logger.warning("Index not initialized.")
            return False
        
        doc = document_manager.get_document_by_name(file_name)
        if not doc:
            logger.warning(f"Document {file_name} not found in registry.")
            return False
        
        logger.info(f"Deleting document: {file_name} (hash: {doc.file_hash})")
        
        try:
            # 删除索引中的文档
            for ref_id in doc.ref_doc_ids:
                self.index.delete_ref_doc(ref_id, delete_from_docstore=True)
            
            self._persist_index()
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
        """持久化索引到磁盘"""
        if self.index:
            self.index.storage_context.persist(persist_dir=STORAGE_DIR)
            logger.debug("Index persisted to disk")
    
    def _clear_index(self):
        """清空索引和存储"""
        logger.info("All documents deleted, clearing entire index")
        self.index = None
        # 删除存储目录
        import shutil
        if os.path.exists(STORAGE_DIR):
            shutil.rmtree(STORAGE_DIR)
            os.makedirs(STORAGE_DIR, exist_ok=True)
        logger.info("Index and storage cleared completely")
    
    def get_index(self) -> Optional[VectorStoreIndex]:
        """获取当前索引"""
        return self.index
    
    def is_index_available(self) -> bool:
        """检查索引是否可用"""
        return self.index is not None
    
    def get_corpus_size(self) -> int:
        """获取语料库大小"""
        if not self.index or not hasattr(self.index, 'docstore'):
            return 0
        return len(self.index.docstore.docs)
```

---

### Task 3.2: 创建缓存服务

**Files:**
- Create: `backend/src/service/cache_service.py`

- [ ] **Step 1: 实现CacheService**

```python
import time
from typing import Any, Tuple, Optional
from src.config.settings import settings
from src.utils.logger import logger

class CacheService:
    """缓存服务，管理检索结果的缓存"""
    
    def __init__(self):
        self.cache = {}
        self.cache_timestamps = {}
        self.enabled = settings.rag_config["cache"]["enabled"]
        self.max_size = settings.rag_config["cache"]["max_size"]
        self.ttl_seconds = settings.rag_config["cache"]["ttl_seconds"]
    
    def get(self, key: Tuple[str, int, int]) -> Optional[Any]:
        """从缓存获取结果"""
        if not self.enabled:
            return None
        
        if key in self.cache and key in self.cache_timestamps:
            timestamp = self.cache_timestamps[key]
            if time.time() - timestamp < self.ttl_seconds:
                logger.debug(f"Cache hit for key: {key}")
                return self.cache[key]
            else:
                # 移除过期条目
                del self.cache[key]
                del self.cache_timestamps[key]
        
        return None
    
    def set(self, key: Tuple[str, int, int], value: Any):
        """保存结果到缓存"""
        if not self.enabled:
            return
        
        # LRU淘汰：如果缓存已满，删除最旧的条目
        if len(self.cache) >= self.max_size:
            oldest_key = min(
                self.cache_timestamps.keys(),
                key=lambda k: self.cache_timestamps[k]
            )
            del self.cache[oldest_key]
            del self.cache_timestamps[oldest_key]
            logger.debug(f"Evicted oldest cache entry: {oldest_key}")
        
        self.cache[key] = value
        self.cache_timestamps[key] = time.time()
        logger.debug(f"Cached result for key: {key}")
    
    def clear(self):
        """清空所有缓存"""
        self.cache.clear()
        self.cache_timestamps.clear()
        logger.info("Cache cleared")
    
    def get_cache_stats(self) -> dict:
        """获取缓存统计信息"""
        return {
            "enabled": self.enabled,
            "size": len(self.cache),
            "max_size": self.max_size,
            "ttl_seconds": self.ttl_seconds
        }
```

---

### Task 3.3: 创建检索服务

**Files:**
- Create: `backend/src/service/retrieval_service.py`

- [ ] **Step 1: 实现RetrievalService**

```python
import jieba
from typing import List, Optional
from llama_index.core.retrievers import BaseRetriever
from llama_index.retrievers.bm25 import BM25Retriever
from llama_index.llms.dashscope import DashScope
from src.config.settings import settings
from src.utils.logger import logger
from src.core.hybrid_retrieval import HybridRetrievalMerger
from src.model.schemas import KnowledgeItem
from src.core.prompts import QUERY_REWRITE_PROMPT, SYNONYM_EXPANSION_PROMPT
from src.service.index_manager_service import IndexManagerService
from src.service.cache_service import CacheService

class RetrievalService:
    """检索服务，处理所有检索相关逻辑"""
    
    def __init__(self, index_manager: IndexManagerService, cache_service: CacheService):
        self.index_manager = index_manager
        self.cache_service = cache_service
        self.bm25_retriever: Optional[BaseRetriever] = None
        self.vector_retriever: Optional[BaseRetriever] = None
        self.bm25_weight = 0.5
        self.vector_weight = 0.5
        self.merge_mode = "OR"
        
        self.dashscope_available = bool(settings.dashscope_api_key)
        self._initialize_retrievers()
    
    def _initialize_retrievers(self):
        """初始化BM25和向量检索器"""
        index = self.index_manager.get_index()
        if not index:
            return
        
        rag_config = settings.rag_config["hybrid_retrieval"]
        corpus_size = self.index_manager.get_corpus_size()
        
        if corpus_size == 0:
            logger.warning("Index is empty. Skipping retriever initialization.")
            self.bm25_retriever = None
            self.vector_retriever = None
            return
        
        # 动态调整top_k
        bm25_top_k = min(rag_config["bm25_top_k"], max(1, corpus_size))
        vector_top_k = min(rag_config["vector_top_k"], max(1, corpus_size))
        
        # 初始化BM25检索器（使用jieba分词）
        self.bm25_retriever = BM25Retriever.from_defaults(
            index=index,
            similarity_top_k=bm25_top_k,
            tokenizer=jieba.lcut
        )
        
        # 初始化向量检索器
        self.vector_retriever = index.as_retriever(
            similarity_top_k=vector_top_k
        )
        
        self.bm25_weight = rag_config["bm25_weight"]
        self.vector_weight = rag_config["vector_weight"]
        self.merge_mode = rag_config["merge_mode"]
        
        logger.info(f"Retrievers initialized: BM25 top_k={bm25_top_k}, Vector top_k={vector_top_k}")
    
    def reload_retrievers(self):
        """重新加载检索器（索引更新后调用）"""
        self._initialize_retrievers()
        self.cache_service.clear()
        logger.info("Retrievers reloaded")
    
    async def retrieve_knowledge(
        self,
        query: str,
        age: int,
        limit: int = 3
    ) -> List[KnowledgeItem]:
        """
        根据查询和年龄检索相关知识点
        """
        logger.info(f"Retrieving knowledge for query: '{query}', age: {age}")
        
        # 检查缓存
        cache_key = self._get_cache_key(query, age, limit)
        cached_result = self.cache_service.get(cache_key)
        if cached_result:
            return cached_result
        
        # 查询重写和同义词扩展
        rewritten_query = await self._rewrite_query(query, age)
        expanded_query = await self._expand_synonyms(rewritten_query)
        
        index = self.index_manager.get_index()
        if not index:
            logger.warning("Index not available, returning empty results.")
            return []
        
        try:
            # 构建年龄过滤器
            filters = self._build_age_filters(age)
            results = await self._execute_retrieval(
                query=expanded_query,
                filters=filters,
                limit=limit,
                use_hybrid=self.bm25_retriever is not None and self.vector_retriever is not None
            )
            
            # 转换为KnowledgeItem
            knowledge_items = self._convert_to_knowledge_items(results)
            
            # 保存到缓存
            self.cache_service.set(cache_key, knowledge_items)
            
            return knowledge_items
            
        except Exception as e:
            logger.error(f"Error during retrieval: {e}", exc_info=True)
            return []
    
    async def search_content(
        self,
        query: str,
        limit: int = 20
    ) -> List[dict]:
        """
        搜索知识库内容，返回匹配的片段和元数据
        """
        if not self.index_manager.is_index_available():
            logger.warning("Index not available, returning empty results.")
            return []
        
        try:
            # 同义词扩展
            expanded_query = await self._expand_synonyms(query)
            
            # 执行检索
            if self.bm25_retriever and self.vector_retriever:
                # 并行检索
                bm25_nodes = await self.bm25_retriever.aretrieve(expanded_query)
                vector_nodes = await self.vector_retriever.aretrieve(expanded_query)
                
                # 使用搜索专用的合并逻辑
                nodes = HybridRetrievalMerger.merge_for_search(
                    bm25_nodes,
                    vector_nodes,
                    bm25_weight=settings.rag_search_bm25_weight,
                    vector_weight=settings.rag_search_vector_weight,
                    no_match_vector_penalty=settings.rag_search_no_match_vector_penalty,
                    limit=limit
                )
            else:
                # 回退到单一向量检索
                corpus_size = self.index_manager.get_corpus_size()
                adjusted_limit = min(limit, max(1, corpus_size))
                retriever = self.index_manager.get_index().as_retriever(
                    similarity_top_k=adjusted_limit
                )
                nodes = await retriever.aretrieve(expanded_query)
            
            # 处理和过滤结果
            processed_results = self._process_search_results(nodes, query, expanded_query)
            
            return processed_results
            
        except Exception as e:
            logger.error(f"Error during content search: {e}", exc_info=True)
            return []
    
    def _build_age_filters(self, age: int):
        """构建年龄过滤器"""
        if age <= 0:
            return None
        
        from llama_index.core.vector_stores import MetadataFilter, MetadataFilters, FilterOperator
        
        filters = [
            MetadataFilter(
                key="target_age_min", value=age, operator=FilterOperator.LTE
            ),
            MetadataFilter(
                key="target_age_max", value=age, operator=FilterOperator.GTE
            )
        ]
        
        return MetadataFilters(filters=filters)
    
    async def _execute_retrieval(self, query: str, filters, limit: int, use_hybrid: bool):
        """执行检索逻辑"""
        if use_hybrid:
            # 设置过滤器
            self.bm25_retriever.filters = filters
            self.vector_retriever.filters = filters
            
            # 并行检索
            bm25_nodes = await self.bm25_retriever.aretrieve(query)
            vector_nodes = await self.vector_retriever.aretrieve(query)
            
            # 合并结果
            nodes = HybridRetrievalMerger.merge_results(
                bm25_nodes,
                vector_nodes,
                bm25_weight=self.bm25_weight,
                vector_weight=self.vector_weight,
                merge_mode=self.merge_mode,
                limit=limit
            )
        else:
            # 回退到单一向量检索
            corpus_size = self.index_manager.get_corpus_size()
            adjusted_limit = min(limit, max(1, corpus_size))
            retriever = self.index_manager.get_index().as_retriever(
                similarity_top_k=adjusted_limit,
                filters=filters
            )
            nodes = await retriever.aretrieve(query)
        
        return nodes
    
    def _convert_to_knowledge_items(self, nodes) -> List[KnowledgeItem]:
        """将检索节点转换为KnowledgeItem"""
        results = []
        for node_with_score in nodes:
            node = node_with_score.node
            content = node.metadata.get("content", node.get_content())
            
            # 过滤无效内容
            if not content or content.startswith("[General Information]") or "书名=" in content or "SS号=" in content:
                continue
            
            # 最低相似度阈值过滤
            score = node_with_score.score or 0.0
            if score < settings.rag_search_min_similarity_threshold:
                continue
            
            metadata = node.metadata or {}
            source = metadata.get("file_name", "Unknown Source")
            
            # 提取元数据字段
            brain_regions = metadata.get("brain_regions", [])
            topics = metadata.get("topics", [])
            benefits = metadata.get("benefits", topics)  # 兼容旧数据
            target_age_min = metadata.get("target_age_min", 0)
            target_age_max = metadata.get("target_age_max", 18)
            activity_type = metadata.get("activity_type", "Theory")
            chapter_title = metadata.get("chapter_title")
            page_label = metadata.get("page_label")
            
            item = KnowledgeItem(
                content=content.strip(),
                source_book=source,
                chapter_title=chapter_title,
                page_label=page_label,
                topics=topics,
                brain_regions=brain_regions,
                benefits=benefits,
                risk_level="Low",
                target_age_min=target_age_min,
                target_age_max=target_age_max,
                activity_type=activity_type,
                relevance_score=float(score),
            )
            results.append(item)
        
        return results
    
    def _process_search_results(self, nodes, original_query: str, expanded_query: str) -> List[dict]:
        """处理搜索结果，包括过滤、评分调整等"""
        if not nodes:
            return []
        
        # 阈值设置
        is_hybrid = self.bm25_retriever is not None and self.vector_retriever is not None
        threshold = settings.rag_search_score_threshold_hybrid if is_hybrid else settings.rag_search_score_threshold_vector
        
        # 动态截断：如果最高分低于阈值，直接返回空
        top_score = nodes[0].score or 0.0
        if top_score < threshold:
            logger.debug(f"Top result score {top_score} below threshold {threshold}, returning empty")
            return []
        
        # 相对分数截断
        relative_cutoff = top_score * settings.rag_search_relative_cutoff_ratio
        
        # 关键词匹配检查
        original_keywords = set(jieba.lcut(original_query.lower()))
        expanded_keywords = set(jieba.lcut(expanded_query.lower()))
        stop_words = {"的", "了", "是", "我", "你", "他", "我们", "你们", "他们", "什么", "怎么", "如何", "为什么", "吗", "呢"}
        original_keywords = {kw for kw in original_keywords if len(kw) > 1 and kw not in stop_words}
        all_keywords = original_keywords.union(expanded_keywords)
        all_keywords = {kw for kw in all_keywords if len(kw) > 1 and kw not in stop_words}
        
        results = []
        from src.service.document_manager import document_manager
        
        for node_with_score in nodes:
            node = node_with_score.node
            metadata = node.metadata or {}
            content = node.get_content()
            
            # 过滤无效内容
            if not content or content.startswith("[General Information]") or "书名=" in content or "SS号=" in content or "参考文献" in content:
                continue
            
            # 阈值过滤
            raw_score = float(node_with_score.score or 0.0)
            if raw_score < threshold or raw_score < relative_cutoff:
                continue
            
            # 关键词匹配检查
            if all_keywords:
                content_lower = content.lower()
                has_keyword = any(kw in content_lower for kw in all_keywords)
                if not has_keyword:
                    continue
            
            # 原始关键词匹配加成
            keyword_bonus = 0.0
            if original_keywords:
                content_lower = content.lower()
                matched_original = sum(1 for kw in original_keywords if kw in content_lower)
                original_match_ratio = matched_original / len(original_keywords) if original_keywords else 0
                keyword_bonus = original_match_ratio * 0.2
            
            final_score = min(raw_score + keyword_bonus, 1.0)
            
            # 获取源书名
            file_hash = metadata.get("file_hash")
            source_book = metadata.get("file_name", "Unknown Source")
            if file_hash:
                doc = document_manager.get_document(file_hash)
                if doc:
                    source_book = doc.file_name
            
            # 处理页码显示
            page_label = metadata.get("page_label")
            if page_label:
                if "index_split" in str(page_label) or ".html" in str(page_label):
                    page_label = metadata.get("chapter_title") or "Section"
                elif len(str(page_label)) > 10 and not str(page_label).isdigit():
                    page_label = f"章节: {page_label}"
            
            results.append({
                "id": node.node_id,
                "content": content,
                "score": final_score,
                "source_book": source_book,
                "chapter_title": metadata.get("chapter_title"),
                "page_label": page_label,
                "target_age_min": metadata.get("target_age_min", 0),
                "target_age_max": metadata.get("target_age_max", 18),
                "brain_regions": metadata.get("brain_regions", []),
                "topics": metadata.get("topics", []),
                "file_hash": metadata.get("file_hash"),
            })
        
        return results
    
    async def _rewrite_query(self, query: str, age: int) -> str:
        """重写查询以提高检索准确率"""
        if not settings.rag_config["query_rewrite"]["enabled"] or not self.dashscope_available:
            return query
        
        try:
            llm = DashScope(
                model=settings.llm_models["query_rewrite"],
                api_key=settings.dashscope_api_key,
            )
            prompt = QUERY_REWRITE_PROMPT.format(query=query, age=age)
            response = await llm.acomplete(prompt)
            rewritten_query = response.text.strip()
            logger.info(f"Query rewritten: '{query}' -> '{rewritten_query}'")
            return rewritten_query if rewritten_query else query
        except Exception as e:
            logger.warning(f"Query rewrite failed: {e}, using original query")
            return query
    
    async def _expand_synonyms(self, query: str) -> str:
        """同义词扩展以提高召回率"""
        if not self.dashscope_available:
            return query
        
        try:
            llm = DashScope(
                model=settings.llm_models["query_rewrite"],
                api_key=settings.dashscope_api_key,
            )
            prompt = SYNONYM_EXPANSION_PROMPT.format(query=query)
            response = await llm.acomplete(prompt)
            synonyms = response.text.strip()
            logger.info(f"Query expanded: '{query}' -> '{synonyms}'")
            return synonyms
        except Exception as e:
            logger.warning(f"Synonym expansion failed: {e}, using original query")
            return query
    
    @staticmethod
    def _get_cache_key(query: str, age: int, limit: int) -> Tuple[str, int, int]:
        """生成缓存键"""
        return (query.strip().lower(), age, limit)
```

---

### Task 3.4: 创建文档导入服务

**Files:**
- Create: `backend/src/service/document_ingestion_service.py`

- [ ] **Step 1: 实现DocumentIngestionService**

```python
import os
import hashlib
import re
import asyncio
from typing import Optional, Callable
from llama_index.core.schema import Document
from src.config.settings import settings
from src.utils.logger import logger
from src.core.parsers import get_parser, PDFParser, PDFVLParser
from src.core.metadata_processor import MetadataProcessor
from src.model.document import DocumentRecord, DocumentMetadata
from src.service.document_manager import document_manager
from src.service.index_manager_service import IndexManagerService
from src.service.retrieval_service import RetrievalService

class DocumentIngestionService:
    """文档导入服务，负责文档的解析、分块、元数据提取、索引插入"""
    
    def __init__(
        self,
        index_manager: IndexManagerService,
        retrieval_service: RetrievalService
    ):
        self.index_manager = index_manager
        self.retrieval_service = retrieval_service
        self.metadata_processor = MetadataProcessor()
    
    async def ingest_book(
        self,
        file_path: str,
        original_filename: str = None,
        progress_callback: Callable[[str, float, str], None] = None
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
        
        file_name = original_filename if original_filename else os.path.basename(file_path)
        logger.info(f"Ingesting book: {file_path} as {file_name}")
        
        # 1. 去重检查
        file_hash = self._calculate_file_hash(file_path)
        if document_manager.exists(file_hash):
            logger.warning(f"Document {file_path} already exists (hash: {file_hash}). Skipping ingestion.")
            return
        
        try:
            # 获取PDF实际总页数
            actual_total_pages = None
            if file_path.lower().endswith('.pdf'):
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
                raise ValueError("无法从文件中提取文本。该文件可能是扫描版PDF或空文件，且无法使用VL模型识别。")
            
            logger.info(f"Parsed {len(documents)} document chunks/pages.")
            
            # 计算章节数
            chapter_count = self._calculate_chapter_count(file_path, documents)
            
            if progress_callback:
                progress_msg = f"文件解析完成，共{chapter_count}章" if chapter_count else f"文件解析完成，共{len(documents)}页"
                progress_callback("chunking", 30.0, f"{progress_msg}，正在分块处理")
            
            # 清理文档内容
            documents = self._clean_documents(documents, file_name)
            
            # 3. 分块处理
            is_epub = file_path.lower().endswith('.epub')
            is_pdf_with_bookmarks = file_path.lower().endswith('.pdf') and documents and 'toc_level' in documents[0].metadata
            
            if is_epub or is_pdf_with_bookmarks:
                # 章节+段落分块
                file_type = "EPUB" if is_epub else "PDF with bookmarks"
                logger.info(f"Using chapter + paragraph based chunking for {file_type} file")
                all_nodes = MetadataProcessor.split_chapters_into_chunks(
                    documents,
                    chunk_target_size=settings.rag_epub_chunk_target_size,
                    file_hash=file_hash
                )
            else:
                # 普通页面分块
                all_nodes = MetadataProcessor.split_pages_into_chunks(
                    documents,
                    chunk_size=settings.rag_pdf_chunk_size,
                    chunk_overlap=settings.rag_chunk_overlap,
                    file_hash=file_hash
                )
            
            # 4. 创建处理中的文档记录
            pending_doc = DocumentRecord(
                file_hash=file_hash,
                file_name=file_name,
                ref_doc_ids=[file_hash],
                metadata=DocumentMetadata(
                    title=file_name,
                    total_pages=actual_total_pages if actual_total_pages is not None else len(documents)
                ),
                status="processing",
                progress=0.0
            )
            document_manager.add_document(pending_doc)
            
            # 5. 元数据提取
            if progress_callback:
                progress_callback("metadata_extraction", 30.0, f"正在提取元数据：0/{len(all_nodes)} 个块")
            
            # 包装进度回调
            async def wrapped_progress(stage: str, progress: float, message: str):
                if progress_callback:
                    # 元数据提取占60%进度（30%到90%）
                    overall_progress = 30.0 + (progress * 0.6)
                    pending_doc.progress = overall_progress
                    document_manager.add_document(pending_doc)
                    progress_callback("embedding", overall_progress, message)
            
            processed_nodes = await self.metadata_processor.process_nodes(
                all_nodes,
                file_hash=file_hash,
                progress_callback=wrapped_progress,
                total_chunks=len(all_nodes)
            )
            
            # 6. 索引构建
            if progress_callback:
                progress_callback("indexing", 90.0, "向量生成完成，正在构建索引")
            
            self.index_manager.insert_nodes(processed_nodes)
            
            # 重新加载检索器
            self.retrieval_service.reload_retrievers()
            
            # 7. 标记为已完成
            doc_record = DocumentRecord(
                file_hash=file_hash,
                file_name=file_name,
                ref_doc_ids=[file_hash],
                metadata=DocumentMetadata(
                    title=file_name,
                    total_pages=actual_total_pages if actual_total_pages is not None else len(documents),
                    chapter_count=chapter_count
                ),
                status="indexed",
                progress=100.0
            )
            document_manager.add_document(doc_record)
            
            logger.info(f"Successfully ingested {file_path}")
            if progress_callback:
                progress_callback("completed", 100.0, "文档导入完成")
        
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
                        total_pages=actual_total_pages if 'actual_total_pages' in locals() else 0
                    ),
                    status="failed",
                    progress=0.0
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
    
    def _check_and_use_vl_parsing(self, file_path: str, documents: list, parser_cls) -> list:
        """检查PDF提取质量，必要时使用VL解析"""
        if parser_cls != PDFParser or not documents:
            return documents
        
        # 获取PDF总页数
        total_pages = documents[0].metadata.get("total_pages", len(documents))
        # 计算平均文本长度
        total_text_length = sum(len(doc.text) for doc in documents)
        avg_text_length = total_text_length / len(documents) if len(documents) > 0 else 0
        
        # 判断是否为扫描版PDF
        extraction_rate = len(documents) / total_pages if total_pages > 0 else 0
        is_scanned_pdf = (extraction_rate < settings.rag_ocr_extraction_rate_threshold or 
                         avg_text_length < settings.rag_ocr_min_avg_length_threshold)
        
        if is_scanned_pdf:
            logger.warning(
                f"PDF extraction rate low ({extraction_rate:.0%}, avg length {avg_text_length:.0f}). "
                f"Trying VL parsing for scanned PDF..."
            )
            try:
                vl_documents = PDFVLParser.parse(file_path)
                if vl_documents:
                    logger.info(f"VL parsing succeeded, extracted {len(vl_documents)} pages")
                    return vl_documents
                else:
                    logger.warning("VL parsing returned empty results, keeping original extraction")
            except Exception as e:
                logger.error(f"VL Parsing failed: {str(e)}")
        
        return documents
    
    def _calculate_chapter_count(self, file_path: str, documents: list) -> Optional[int]:
        """计算文档的章节数"""
        is_epub = file_path.lower().endswith('.epub')
        is_pdf_with_bookmarks = file_path.lower().endswith('.pdf') and documents and 'toc_level' in documents[0].metadata
        
        if is_epub or is_pdf_with_bookmarks:
            return len(documents)
        
        return None
    
    def _clean_documents(self, documents: list, file_name: str) -> list:
        """清理文档内容，移除多余空白字符"""
        cleaned_documents = []
        for doc in documents:
            # 清理多余的换行和空格
            cleaned_text = re.sub(r'\n\s*\n', '\n\n', doc.text)
            cleaned_text = re.sub(r' +', ' ', cleaned_text)
            cleaned_text = cleaned_text.strip()
            
            # 创建新文档
            new_doc = Document(
                text=cleaned_text,
                metadata=doc.metadata.copy()
            )
            
            new_doc.metadata["file_name"] = file_name
            # 确保page_label存在
            if "page_label" not in new_doc.metadata:
                new_doc.metadata["page_label"] = new_doc.metadata.get("chapter_title", "Unknown")
            
            cleaned_documents.append(new_doc)
        
        return cleaned_documents
```

---

## Task 4: 重构原有RagService，保持接口兼容

**Files:**
- Modify: `backend/src/service/rag_service.py`

- [ ] **Step 1: 重构RagService为门面模式，委托给各个子服务**

```python
from typing import List
from src.service.index_manager_service import IndexManagerService
from src.service.cache_service import CacheService
from src.service.retrieval_service import RetrievalService
from src.service.document_ingestion_service import DocumentIngestionService
from src.utils.logger import logger

# 单例实例
index_manager = IndexManagerService()
cache_service = CacheService()
retrieval_service = RetrievalService(index_manager, cache_service)
document_ingestion_service = DocumentIngestionService(index_manager, retrieval_service)

class RagService:
    """
    RAG服务门面类，保持原有接口不变，内部委托给各个子服务
    用于向后兼容，新代码建议直接使用各个子服务
    """
    
    def __init__(self):
        self.index_manager = index_manager
        self.cache_service = cache_service
        self.retrieval_service = retrieval_service
        self.document_ingestion_service = document_ingestion_service
        logger.info("RagService initialized with split architecture")
    
    @property
    def index(self):
        """兼容原有代码对index的直接访问"""
        return self.index_manager.get_index()
    
    async def retrieve_knowledge(self, query: str, age: int, limit: int = 3):
        """检索知识点（原有接口）"""
        return await self.retrieval_service.retrieve_knowledge(query, age, limit)
    
    async def ingest_book(self, file_path: str, original_filename: str = None, progress_callback=None):
        """导入书籍（原有接口）"""
        return await self.document_ingestion_service.ingest_book(file_path, original_filename, progress_callback)
    
    def delete_document(self, file_name: str) -> bool:
        """删除文档（原有接口）"""
        success = self.index_manager.delete_document(file_name)
        if success:
            self.retrieval_service.reload_retrievers()
        return success
    
    async def search_content(self, query: str, limit: int = 20) -> List[dict]:
        """搜索内容（原有接口）"""
        return await self.retrieval_service.search_content(query, limit)
    
    def _initialize_index(self):
        """兼容原有初始化方法"""
        logger.warning("_initialize_index is deprecated, index is managed by IndexManagerService")
    
    def _initialize_retrievers(self):
        """兼容原有检索器初始化方法"""
        logger.warning("_initialize_retrievers is deprecated, retrievers are managed by RetrievalService")
        self.retrieval_service.reload_retrievers()
    
    def _clear_cache(self):
        """兼容原有缓存清除方法"""
        logger.warning("_clear_cache is deprecated, cache is managed by CacheService")
        self.cache_service.clear()

# 保持原有单例接口不变
rag_service = RagService()
```

---

## Task 5: 验证重构正确性

**Files:**
- Test: `backend/tests/test_rag_refactoring.py`

- [ ] **Step 1: 创建集成测试**

```python
import pytest
import asyncio
import os
import tempfile
from src.service.rag_service import rag_service

@pytest.mark.asyncio
async def test_rag_service_interface_compatibility():
    """测试RagService接口兼容性，确保重构后原有功能正常"""
    
    # 测试检索功能（索引为空时返回空列表）
    results = await rag_service.retrieve_knowledge("测试查询", age=3)
    assert isinstance(results, list)
    assert len(results) == 0
    
    # 测试搜索功能
    search_results = await rag_service.search_content("测试搜索")
    assert isinstance(search_results, list)
    assert len(search_results) == 0
    
    # 测试删除不存在的文档
    delete_result = rag_service.delete_document("不存在的文档.pdf")
    assert delete_result is False

@pytest.mark.asyncio
async def test_document_ingestion_workflow():
    """测试文档导入工作流（需要测试PDF文件）"""
    # 创建一个简单的测试PDF文件
    test_pdf_content = """%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R >>
endobj
4 0 obj
<< /Length 55 >>
stream
BT
/F1 24 Tf
100 700 Td
(Hello World) Tj
ET
endstream
endobj
xref
0 5
0000000000 65535 f 
0000000009 00000 n 
0000000074 00000 n 
0000000129 00000 n 
0000000227 00000 n 
trailer
<< /Size 5 /Root 1 0 R >>
startxref
334
%%EOF
"""
    
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(test_pdf_content.encode('latin1'))
        tmp_path = tmp.name
    
    try:
        # 测试导入功能（没有API Key时会失败，但应该能走到解析步骤）
        try:
            await rag_service.ingest_book(tmp_path, "test.pdf")
        except Exception as e:
            # 预期会因为没有API Key失败，但不应该崩溃
            assert "DashScope API Key" in str(e) or "元数据提取" in str(e)
    
    finally:
        os.unlink(tmp_path)

def test_service_instances():
    """测试各个服务实例是否正确初始化"""
    assert rag_service.index_manager is not None
    assert rag_service.cache_service is not None
    assert rag_service.retrieval_service is not None
    assert rag_service.document_ingestion_service is not None
```

- [ ] **Step 2: 运行所有相关测试**
```bash
cd backend
uv run pytest tests/test_rag* -v
```
Expected: All existing tests pass, new tests pass

- [ ] **Step 3: 启动服务验证功能**
```bash
cd backend
uv run python src/server.py
```
Expected: Service starts successfully, no errors

---

## 验证标准
1. ✅ 原有接口完全兼容，现有代码不需要修改
2. ✅ 三个架构问题都得到解决：
   - RagService已拆分为多个单一职责服务
   - 混合检索逻辑已提取到HybridRetrievalMerger，统一了两处实现
   - process_node重复代码已消除，由MetadataProcessor统一处理
3. ✅ 所有原有测试通过
4. ✅ 服务启动正常，功能可用

Plan complete and saved to `docs/superpowers/plans/2026-03-13-rag-architecture-refactoring-plan.md`. Ready to execute?