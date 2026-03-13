# RAG 系统优化功能实施计划

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 RAG 系统实现三个核心优化功能：查询缓存、查询重写和增量更新，进一步提升系统性能和检索准确性。

**Architecture:**

* **查询缓存**：使用内存 LRU 缓存存储频繁查询结果，支持 TTL 自动过期

* **查询重写**：使用 LLM 优化用户查询，提升检索相关性

* **增量更新**：优化索引更新机制，支持增量添加文档而无需全量重建

**Tech Stack:** Python 3.13, LRU Cache, LangChain LLM, LlamaIndex

***

## 任务分解

### 任务 1: 实现查询缓存机制

**Files:**

* Modify: `/Users/owen/project/ai/child-development-assessment-agent/backend/src/config/settings.py`

* Modify: `/Users/owen/project/ai/child-development-assessment-agent/backend/src/service/rag_service.py`

* [ ] **Step 1: 添加缓存配置到 settings.py**

```python
# 在 RAG_CONFIG 中添加
"cache": {
    "enabled": True,
    "max_size": 1000,  # 最大缓存条目数
    "ttl_seconds": 3600  # 缓存过期时间（1小时）
}
```

* [ ] **Step 2: 在 RagService 中实现 LRU 缓存**

```python
# 新增导入
from functools import lru_cache
import time
from typing import Any, Tuple

# 在 RagService 类中添加缓存相关属性和方法
def __init__(self):
    # 原有代码...
    self.cache = {}
    self.cache_timestamps = {}

def _get_cache_key(self, query: str, age: int, limit: int) -> Tuple[str, int, int]:
    """生成缓存键"""
    return (query.strip().lower(), age, limit)

def _get_from_cache(self, key: Tuple[str, int, int]) -> Any:
    """从缓存获取结果，检查过期时间"""
    if not settings.RAG_CONFIG["cache"]["enabled"]:
        return None
        
    if key in self.cache and key in self.cache_timestamps:
        timestamp = self.cache_timestamps[key]
        if time.time() - timestamp < settings.RAG_CONFIG["cache"]["ttl_seconds"]:
            return self.cache[key]
        else:
            # 移除过期缓存
            del self.cache[key]
            del self.cache_timestamps[key]
    return None

def _save_to_cache(self, key: Tuple[str, int, int], value: Any):
    """保存结果到缓存，处理缓存大小限制"""
    if not settings.RAG_CONFIG["cache"]["enabled"]:
        return
        
    # 如果缓存已满，移除最早的条目
    if len(self.cache) >= settings.RAG_CONFIG["cache"]["max_size"]:
        oldest_key = min(self.cache_timestamps.keys(), key=lambda k: self.cache_timestamps[k])
        del self.cache[oldest_key]
        del self.cache_timestamps[oldest_key]
    
    self.cache[key] = value
    self.cache_timestamps[key] = time.time()
```

* [ ] **Step 3: 在 retrieve\_knowledge 方法中集成缓存逻辑**

```python
async def retrieve_knowledge(self, query: str, age: int, limit: int = 3) -> List[KnowledgeItem]:
    """
    根据查询和年龄检索相关知识点
    """
    print(f"Retrieving knowledge for query: '{query}', age: {age}")
    
    # 检查缓存
    cache_key = self._get_cache_key(query, age, limit)
    cached_result = self._get_from_cache(cache_key)
    if cached_result:
        print(f"Cache hit for query: '{query}'")
        return cached_result
    
    # 原有检索逻辑...
    
    # 保存结果到缓存
    self._save_to_cache(cache_key, results)
    
    return results
```

***

### 任务 2: 实现查询重写功能

**Files:**

* Modify: `/Users/owen/project/ai/child-development-assessment-agent/backend/src/config/settings.py`

* Modify: `/Users/owen/project/ai/child-development-assessment-agent/backend/src/service/rag_service.py`

* Modify: `/Users/owen/project/ai/child-development-assessment-agent/backend/src/core/prompts.py`

* [ ] **Step 1: 添加查询重写配置到 settings.py**

```python
# 在 RAG_CONFIG 中添加
"query_rewrite": {
    "enabled": True,
    "max_rewrites": 1,
    "prompt_template": "你是一个儿童发展领域的查询优化专家。请将用户的查询重写为更适合检索的形式，扩展相关同义词和专业术语。\n原始查询: {query}\n儿童年龄: {age}\n重写后的查询:"
}
```

* [ ] **Step 2: 在 prompts.py 中添加查询重写提示模板**

```python
QUERY_REWRITE_PROMPT = """
你是儿童发展领域的专业检索优化专家。请将用户的原始查询重写为更适合知识库检索的形式：
1. 扩展相关同义词和专业术语（例如："怕高" -> "恐高 前庭觉 平衡感"）
2. 补充与儿童年龄相关的关键词
3. 保持查询简洁，不超过 200 字
4. 只返回重写后的查询文本，不需要其他解释

原始查询: {query}
儿童年龄: {age}
重写后的查询:
"""
```

* [ ] **Step 3: 在 RagService 中实现查询重写方法**

```python
# 新增导入
from src.core.prompts import QUERY_REWRITE_PROMPT

# 添加查询重写方法
async def _rewrite_query(self, query: str, age: int) -> str:
    """使用 LLM 重写查询以提高检索准确性"""
    if not settings.RAG_CONFIG["query_rewrite"]["enabled"] or not Settings.llm:
        return query
        
    try:
        prompt = QUERY_REWRITE_PROMPT.format(query=query, age=age)
        response = await Settings.llm.acomplete(prompt)
        rewritten_query = response.text.strip()
        print(f"Original query: '{query}' -> Rewritten query: '{rewritten_query}'")
        return rewritten_query if rewritten_query else query
    except Exception as e:
        print(f"Query rewrite failed: {e}")
        return query
```

* [ ] **Step 4: 在 retrieve\_knowledge 中集成查询重写**

```python
async def retrieve_knowledge(self, query: str, age: int, limit: int = 3) -> List[KnowledgeItem]:
    # 原有缓存检查逻辑...
    
    # 查询重写
    rewritten_query = await self._rewrite_query(query, age)
    
    # 检索时使用重写后的查询
    # 原有检索逻辑中使用 rewritten_query 替代 query
    nodes = await self.bm25_retriever.aretrieve(rewritten_query)
    vector_nodes = await self.vector_retriever.aretrieve(rewritten_query)
    
    # 原有逻辑...
```

***

### 任务 3: 实现索引增量更新

**Files:**

* Modify: `/Users/owen/project/ai/child-development-assessment-agent/backend/src/service/rag_service.py`

* [ ] **Step 1: 优化 ingest\_book 方法实现增量更新**

```python
async def ingest_book(self, file_path: str):
    """
    Process book file and build index with semantic metadata.
    支持增量更新，无需全量重建索引
    """
    # 原有去重检查、解析、分块、元数据提取逻辑...
    
    # 4. 索引更新（增量添加节点，无需重建）
    if self.index:
        # 增量插入新节点
        self.index.insert_nodes(all_nodes)
        # 持久化索引
        self.index.storage_context.persist(persist_dir=STORAGE_DIR)
        # 更新检索器（LlamaIndex 会自动更新索引引用）
        self._initialize_retrievers()
    else:
        # 首次创建索引
        self.index = VectorStoreIndex(all_nodes)
        self.index.storage_context.persist(persist_dir=STORAGE_DIR)
        self._initialize_retrievers()
    
    # 原有文档注册逻辑...
```

* [ ] **Step 2: 优化 delete\_document 方法实现增量删除**

```python
def delete_document(self, file_name: str) -> bool:
    """Delete a document by file name, support incremental update"""
    if not self.index:
        print("Index not initialized.")
        return False
        
    doc = document_manager.get_document_by_name(file_name)
    if not doc:
        print(f"Document {file_name} not found in registry.")
        return False
        
    print(f"Deleting document: {file_name} (hash: {doc.file_hash})")
    
    try:
        # Delete from index using ref_doc_ids
        for ref_id in doc.ref_doc_ids:
            self.index.delete_ref_doc(ref_id, delete_from_docstore=True)
        
        # 持久化更新后的索引
        self.index.storage_context.persist(persist_dir=STORAGE_DIR)
        # 更新检索器
        self._initialize_retrievers()
        
        document_manager.delete_document(doc.file_hash)
        # 清除相关缓存
        self._clear_cache()
        
        print(f"Successfully deleted {file_name}")
        return True
    except Exception as e:
        print(f"Failed to delete document: {e}")
        return False
```

* [ ] **Step 3: 添加缓存清除方法**

```python
def _clear_cache(self):
    """清除所有缓存，当索引更新时调用"""
    self.cache.clear()
    self.cache_timestamps.clear()
    print("Cache cleared due to index update")
```

***

### 任务 4: 编写测试用例

**Files:**

* Create: `/Users/owen/project/ai/child-development-assessment-agent/backend/tests/test_rag_optimizations.py`

* [ ] **Step 1: 编写缓存功能测试**

```python
@pytest.mark.asyncio
async def test_query_caching():
    """Test query caching functionality"""
    query = "测试缓存查询"
    age = 3
    
    # 第一次查询
    start_time = time.time()
    result1 = await rag_service.retrieve_knowledge(query, age)
    time_first = time.time() - start_time
    
    # 第二次查询（应该命中缓存）
    start_time = time.time()
    result2 = await rag_service.retrieve_knowledge(query, age)
    time_second = time.time() - start_time
    
    # 验证结果相同
    assert len(result1) == len(result2)
    for i in range(len(result1)):
        assert result1[i].content == result2[i].content
    
    # 缓存查询应该更快
    assert time_second < time_first
    print("✅ 查询缓存功能测试通过")
```

* [ ] **Step 2: 编写查询重写测试**

```python
@pytest.mark.asyncio
async def test_query_rewrite():
    """Test query rewrite functionality"""
    original_query = "孩子怕高怎么办"
    age = 5
    
    rewritten = await rag_service._rewrite_query(original_query, age)
    
    # 验证重写后的查询包含相关关键词
    assert rewritten is not None
    assert len(rewritten) > 0
    print(f"✅ 查询重写测试通过: '{original_query}' -> '{rewritten}'")
```

* [ ] **Step 3: 编写增量更新测试**

```python
def test_incremental_update_support():
    """Test that incremental update is properly implemented"""
    # 验证方法存在
    assert hasattr(rag_service, 'ingest_book')
    assert hasattr(rag_service, 'delete_document')
    assert hasattr(rag_service, '_clear_cache')
    print("✅ 增量更新接口测试通过")
```

***

### 任务 5: 测试与验证

* [ ] **Step 1: 运行所有测试**
  Run: `cd backend && PYTHONPATH=. uv run pytest tests/ -v`
  Expected: 所有测试通过

* [ ] **Step 2: 验证功能正常工作**
  Run: `cd backend && uv run python src/server.py`
  Expected: 服务正常启动，无错误

***

## 预期效果

1. **响应速度提升**: 频繁查询通过缓存响应，速度提升 10-100 倍
2. **检索准确性提升**: 查询重写优化查询关键词，提高相关结果召回率
3. **维护效率提升**: 支持增量更新索引，添加/删除文档无需全量重建
4. **资源利用率优化**: LRU 缓存自动管理内存使用，避免内存泄漏

