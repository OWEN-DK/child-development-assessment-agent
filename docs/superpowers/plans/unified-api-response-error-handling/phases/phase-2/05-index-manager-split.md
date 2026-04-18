# Phase 2-5: IndexManagerService 拆分

> **需求来源**: spec 文档 `unified-api-response-and-error-handling.md` 中 `3.3.5` 节
> **所属 Phase**: Phase 2

## 需求定义

将 `IndexManagerService`（599 行）按单一职责拆分为 4 个子服务 + 1 个门面类。

## 验收标准

- [ ] 单类不超过 200 行
- [ ] 门面类对外 API 保持兼容
- [ ] 子服务通过依赖注入获取
- [ ] 现有测试全部通过

## 涉及文件

| 文件路径 | 操作 | 说明 |
|---------|------|------|
| `backend/src/service/index_manager_service.py` | 删除 | 原 599 行文件 |
| `backend/src/service/index/__init__.py` | 新增 | 模块入口 |
| `backend/src/service/index/lifecycle.py` | 新增 | IndexLifecycleManager（生命周期，~200 行） |
| `backend/src/service/index/persistor.py` | 新增 | IndexPersistor（持久化，~150 行） |
| `backend/src/service/index/operations.py` | 新增 | IndexOperations（插入/删除，~150 行） |
| `backend/src/service/index/chunk_query.py` | 新增 | ChunkQueryService（分块查询，~150 行） |

## 拆分方案

### 职责划分

| 子服务 | 职责 | 原 IndexManagerService 方法 |
|--------|------|---------------------------|
| `IndexLifecycleManager` | 索引初始化、加载、重试 | `init_index`, `load_index`, `retry_load` |
| `IndexPersistor` | 持久化、原子写入、备份 | `persist`, `atomic_write`, `create_backup` |
| `IndexOperations` | 插入、删除、清空 | `add_documents`, `delete_documents`, `clear_index` |
| `ChunkQueryService` | 分块查询、分页、详情 | `get_chunk`, `list_chunks`, `get_chunk_detail` |

### 门面类实现

```python
"""
索引管理门面类

协调各索引子服务，对外提供统一索引管理 API。
"""

from typing import Optional

from src.service.index.lifecycle import IndexLifecycleManager
from src.service.index.persistor import IndexPersistor
from src.service.index.operations import IndexOperations
from src.service.index.chunk_query import ChunkQueryService


class IndexFacade:
    """索引管理门面类"""

    def __init__(
        self,
        lifecycle: IndexLifecycleManager,
        persistor: IndexPersistor,
        operations: IndexOperations,
        chunk_query: ChunkQueryService,
    ):
        self._lifecycle = lifecycle
        self._persistor = persistor
        self._operations = operations
        self._chunk_query = chunk_query

    async def init_index(self) -> bool:
        return await self._lifecycle.init_index()

    async def load_index(self) -> bool:
        return await self._lifecycle.load_index()

    async def persist(self) -> bool:
        return await self._persistor.persist()

    async def add_documents(self, documents: list) -> int:
        return await self._operations.add_documents(documents)

    async def delete_documents(self, ids: list[str]) -> int:
        return await self._operations.delete_documents(ids)

    async def get_chunk(self, chunk_id: str) -> dict:
        return await self._chunk_query.get_chunk(chunk_id)


# 单例
index_facade: Optional[IndexFacade] = None


def get_index_facade() -> IndexFacade:
    global index_facade
    if index_facade is None:
        index_facade = IndexFacade(
            lifecycle=IndexLifecycleManager(),
            persistor=IndexPersistor(),
            operations=IndexOperations(),
            chunk_query=ChunkQueryService(),
        )
    return index_facade
```

## 测试方案

1. 索引初始化/加载正常
2. 持久化原子性正确
3. 增删操作与拆分前一致
4. 分块查询正确

## 注意事项

- 索引持久化需使用原子写入，防止中断导致数据损坏
- 备份机制需保留最近 N 个版本
- ChromaDB 操作需处理并发
