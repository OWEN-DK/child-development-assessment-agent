# RetrievalService 复用实例 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** RetrievalService 复用实例

**Architecture:** 参考下方原文档的实现方案和数据模型

**Tech Stack:** Python, FastAPI, TypeScript, React

---

### Task 1: 实现核心逻辑与测试

**Files:**
- Modify: `backend/src/service/rag_test_manager.py`
- Modify: `backend/src/core/di_container.py`
- Modify: `backend/src/service/retrieval_service.py`
- Test: `backend/src/service/rag_test_manager.py`

- [ ] **Step 1: Write the failing test**
  - 根据下方的验收标准和测试方案，编写对应的测试用例
- [ ] **Step 2: Run test to verify it fails**
  - 执行测试并确保看到预期失败信息 (Red)
- [ ] **Step 3: Write minimal implementation**
  - 根据下方"实现方案"中的步骤，编写或修改业务代码
- [ ] **Step 4: Run test to verify it passes**
  - 执行测试确保通过 (Green)
- [ ] **Step 5: Commit**
  - `git add` 相关文件并提交 commit

---

## 原始需求与设计细节 (供参考)

> **需求来源**: spec 文档 `01-phase-0-bug-fixes.md` 中 `2.0.2` 节
> **所属 Phase**: Phase 0
> **根因**: 每个用例创建新 RetrievalService 实例，并发时耗尽连接池

---

## 需求定义

当前 `execute_test_case` 方法中，每次执行测试用例都直接 `RetrievalService()` 创建新实例。在批量测试（如 128 用例并发）时，会创建大量实例，导致数据库连接池耗尽。

**修复要求**：
1. 批量测试必须复用同一个 RetrievalService 实例
2. 使用 DI 容器或全局单例获取实例
3. 确保线程/协程安全

---

## 验收标准

- [ ] 128 用例测试不出现连接池耗尽错误
- [ ] 所有用例共享同一个 RetrievalService 实例
- [ ] 并发检索结果正确

---

## 涉及文件

| 文件路径 | 操作 | 说明 |
|---------|------|------|
| `backend/src/service/rag_test_manager.py` | 修改 | 使用 DI 容器获取 RetrievalService |
| `backend/src/core/di_container.py` | 检查 | 确认 RetrievalService 已注册为单例 |
| `backend/src/service/retrieval_service.py` | 检查 | 确认线程安全 |

---

## 实现方案

### 后端实现

**步骤 1：确认 DI 容器中 RetrievalService 的注册**

检查 `di_container.py`：

```python
# backend/src/core/di_container.py

from injector import provider, singleton

class ServiceModule(Module):
    @provider
    @singleton
    def provide_retrieval_service(
        self,
        index_manager: IIndexManager,
        cache_service: ICacheService,
    ) -> IRetrievalService:
        return RetrievalService(index_manager, cache_service)
```

确认 `RetrievalService` 已注册为 `@singleton`。

**步骤 2：修改 `rag_test_manager.py` 使用 DI 容器**

方案 A：通过构造函数注入（推荐）

```python
# backend/src/service/rag_test_manager.py

from src.core.interfaces import IRetrievalService

class RagTestManager:
    def __init__(
        self,
        retrieval_service: IRetrievalService,
        # ... 其他依赖
    ):
        self._retrieval_service = retrieval_service
        # ...
    
    async def _execute_single_test_case(self, test_case: dict) -> dict:
        """执行单个测试用例"""
        # 使用注入的实例，而非创建新实例
        results = await self._retrieval_service.search(
            query=test_case['query'],
            age=test_case['age'],
            limit=10,
        )
        
        # ... 评估逻辑
```

方案 B：通过全局 DI 容器获取（如构造函数注入改动过大）

```python
# backend/src/service/rag_test_manager.py

from src.core.di_container import injector
from src.core.interfaces import IRetrievalService

class RagTestManager:
    def __init__(self):
        # 懒加载：首次使用时从 DI 容器获取
        self._retrieval_service: IRetrievalService | None = None
    
    def _get_retrieval_service(self) -> IRetrievalService:
        """获取 RetrievalService 实例（单例）
        
        返回:
            RetrievalService 单例实例
        """
        if self._retrieval_service is None:
            self._retrieval_service = injector.get(IRetrievalService)
        return self._retrieval_service
    
    async def _execute_single_test_case(self, test_case: dict) -> dict:
        retrieval_service = self._get_retrieval_service()
        results = await retrieval_service.search(
            query=test_case['query'],
            age=test_case['age'],
            limit=10,
        )
        # ...
```

**步骤 3：检查 RetrievalService 的线程安全**

确认 `RetrievalService.search()` 方法是异步安全的：

```python
# backend/src/service/retrieval_service.py

class RetrievalService:
    def __init__(self, index_manager: IndexManagerService, cache_service: CacheService):
        self._index_manager = index_manager
        self._cache_service = cache_service
    
    async def search(self, query: str, age: int, limit: int = 10) -> list:
        """检索知识
        
        此方法必须是协程安全的（无共享可变状态）。
        
        参数:
            query: 查询文本
            age: 年龄段
            limit: 返回结果数量
            
        返回:
            检索结果列表
        """
        # 检查缓存
        cache_key = f"search:{query}:{age}:{limit}"
        cached = await self._cache_service.get(cache_key)
        if cached:
            return cached
        
        # 执行检索（LlamaIndex 的检索是协程安全的）
        index = await self._index_manager.get_index(age)
        results = await index.as_retriever(similarity_top_k=limit).aretrieve(query)
        
        # 缓存结果
        await self._cache_service.set(cache_key, results, ttl=3600)
        
        return results
```

如果 `RetrievalService` 内部有共享可变状态（如实例级缓存字典），需加锁保护：

```python
class RetrievalService:
    def __init__(self, ...):
        self._local_cache = {}
        self._lock = asyncio.Lock()
    
    async def search(self, query: str, ...) -> list:
        cache_key = f"{query}:{...}"
        
        async with self._lock:
            if cache_key in self._local_cache:
                return self._local_cache[cache_key]
        
        results = await self._do_search(query, ...)
        
        async with self._lock:
            self._local_cache[cache_key] = results
        
        return results
```

**步骤 4：修改控制器中的 RagTestManager 实例化**

确保 `RagTestManager` 也通过 DI 容器创建：

```python
# backend/src/controller/rag_test_controller.py

from src.core.di_container import injector
from src.service.rag_test_manager import RagTestManager

# 修改前
rag_test_manager = RagTestManager()

# 修改后
rag_test_manager = injector.get(RagTestManager)
```

或在 `di_container.py` 中注册：

```python
class ServiceModule(Module):
    @provider
    @singleton
    def provide_rag_test_manager(
        self,
        retrieval_service: IRetrievalService,
    ) -> RagTestManager:
        """提供 RagTestManager 单例实例
        
        返回:
            RagTestManager 实例（已注入 RetrievalService）
        """
        return RagTestManager(retrieval_service=retrieval_service)
```

---

## 测试方案

### 单元测试

```python
# backend/tests/test_retrieval_service_reuse.py

import pytest
from unittest.mock import AsyncMock, patch

class TestRetrievalServiceReuse:
    @pytest.mark.asyncio
    async def test_same_instance_used(self):
        """测试批量测试中复用同一实例"""
        mock_retrieval = AsyncMock()
        manager = RagTestManager(retrieval_service=mock_retrieval)
        
        # 执行多个用例
        test_cases = [
            {"id": "case-1", "query": "query 1", "age": 5},
            {"id": "case-2", "query": "query 2", "age": 5},
        ]
        
        for tc in test_cases:
            await manager._execute_single_test_case(tc)
        
        # 验证使用的是注入的实例
        assert mock_retrieval.search.call_count == 2
    
    @pytest.mark.asyncio
    async def test_concurrent_search(self):
        """测试并发检索不耗尽连接池"""
        mock_retrieval = AsyncMock()
        mock_retrieval.search.side_effect = lambda **kwargs: [{"result": kwargs["query"]}]
        
        manager = RagTestManager(retrieval_service=mock_retrieval)
        
        # 模拟 128 并发
        tasks = [
            manager._execute_single_test_case({"id": f"case-{i}", "query": f"query {i}", "age": 5})
            for i in range(128)
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 所有任务应该成功
        errors = [r for r in results if isinstance(r, Exception)]
        assert len(errors) == 0
        assert mock_retrieval.search.call_count == 128
```

### 手动测试

1. 创建一个包含 128 个用例的测试集
2. 执行批量测试，并发数设为 10
3. 检查后端日志，确认没有连接池耗尽错误
4. 检查所有用例都有结果返回

---

## 注意事项

1. **DI 容器初始化时机**：确保 DI 容器在应用启动时完成初始化，`RagTestManager` 的依赖在首次使用时可获取。
2. **单例 vs 每请求实例**：`RetrievalService` 作为单例是安全的，因为它是无状态的（或状态通过外部缓存管理）。如果未来需要每请求隔离，可改为 `@transient`。
3. **连接池配置**：检查数据库连接池大小配置，确保能支持预期并发数。MySQL 默认最大连接数 151，需根据实际并发调整。
4. **附带修复**：需求点 7（runSingleTest 严格单用例）中的 `RetrievalService()` 无参数调用 Bug 也在此处一并修复。

---

**返回索引：** [Phase 0 总览](../00-overview.md)
