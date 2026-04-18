# Phase 2-2: RetrievalService 拆分

> **需求来源**: spec 文档 `unified-api-response-and-error-handling.md` 中 `3.3.2` 节
> **所属 Phase**: Phase 2

## 需求定义

将 `RetrievalService`（1096 行）按单一职责拆分为 5 个子服务 + 1 个门面类。

## 验收标准

- [ ] 单类不超过 200 行
- [ ] 门面类对外 API 保持兼容
- [ ] 子服务通过依赖注入获取
- [ ] 现有测试全部通过

## 涉及文件

| 文件路径 | 操作 | 说明 |
|---------|------|------|
| `backend/src/service/retrieval_service.py` | 删除 | 原 1096 行文件 |
| `backend/src/service/retrieval/__init__.py` | 新增 | 模块入口 |
| `backend/src/service/retrieval/orchestrator.py` | 新增 | RetrievalOrchestrator（主流程编排，~200 行） |
| `backend/src/service/retrieval/retriever_init.py` | 新增 | RetrieverInitializer（检索器初始化，~150 行） |
| `backend/src/service/retrieval/query_processor.py` | 新增 | QueryProcessor（查询重写/同义词，~250 行） |
| `backend/src/service/retrieval/result_processor.py` | 新增 | ResultProcessor（结果转换/去重，~250 行） |
| `backend/src/service/retrieval/search_handler.py` | 新增 | SearchResultHandler（搜索专用，~200 行） |

## 拆分方案

### 职责划分

| 子服务 | 职责 | 原 RetrievalService 方法 |
|--------|------|------------------------|
| `RetrievalOrchestrator` | 主检索流程编排，协调各子服务 | `search`, `search_with_config` |
| `RetrieverInitializer` | 检索器初始化、重载、状态管理 | `_init_retrievers`, `reload_index`, `_get_retriever_status` |
| `QueryProcessor` | 查询重写、同义词扩展、意图识别 | `_rewrite_query`, `_expand_synonyms`, `_classify_intent` |
| `ResultProcessor` | 结果转换、去重、评分映射、融合 | `_process_results`, `_deduplicate`, `_map_scores`, `_fuse_results` |
| `SearchResultHandler` | 搜索专用处理、分页、关键词加成 | `search_for_frontend`, `_apply_keyword_boost` |

### 门面类实现

```python
"""
检索编排门面类

协调各子服务，对外提供统一检索 API。
"""

from typing import Optional

from src.service.retrieval.orchestrator import RetrievalOrchestrator
from src.service.retrieval.retriever_init import RetrieverInitializer
from src.service.retrieval.query_processor import QueryProcessor
from src.service.retrieval.result_processor import ResultProcessor
from src.service.retrieval.search_handler import SearchResultHandler


class RetrievalFacade:
    """检索门面类"""

    def __init__(
        self,
        orchestrator: RetrievalOrchestrator,
        retriever_init: RetrieverInitializer,
        query_proc: QueryProcessor,
        result_proc: ResultProcessor,
        search_handler: SearchResultHandler,
    ):
        self._orchestrator = orchestrator
        self._retriever_init = retriever_init
        self._query_proc = query_proc
        self._result_proc = result_proc
        self._search_handler = search_handler

    async def search(self, query: str, **kwargs) -> dict:
        """统一检索入口"""
        return await self._orchestrator.search(query, **kwargs)

    async def reload_index(self) -> bool:
        """重新加载索引"""
        return await self._retriever_init.reload_index()

    async def search_for_frontend(self, query: str, page: int = 1, **kwargs) -> dict:
        """前端搜索专用（含分页、关键词加成）"""
        return await self._search_handler.search_for_frontend(query, page, **kwargs)


# 单例
retrieval_facade: Optional[RetrievalFacade] = None


def get_retrieval_facade() -> RetrievalFacade:
    global retrieval_facade
    if retrieval_facade is None:
        retrieval_facade = RetrievalFacade(
            orchestrator=RetrievalOrchestrator(),
            retriever_init=RetrieverInitializer(),
            query_proc=QueryProcessor(),
            result_proc=ResultProcessor(),
            search_handler=SearchResultHandler(),
        )
    return retrieval_facade
```

## 测试方案

1. 门面类转发调用正确
2. 各子服务单元测试通过
3. 检索结果与拆分前一致
4. 性能测试：检索延迟无退化

## 注意事项

- 检索器初始化涉及 LlamaIndex/Chroma 等重型依赖，需懒加载
- 查询重写可能调用 LLM，需处理超时和降级
- 结果去重需保持原有逻辑不变
