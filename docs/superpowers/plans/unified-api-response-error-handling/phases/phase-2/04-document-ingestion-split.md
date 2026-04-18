# Phase 2-4: DocumentIngestionService 拆分

> **需求来源**: spec 文档 `unified-api-response-and-error-handling.md` 中 `3.3.4` 节
> **所属 Phase**: Phase 2

## 需求定义

将 `DocumentIngestionService`（742 行）按单一职责拆分为 5 个子服务 + 1 个门面类。

## 验收标准

- [ ] 单类不超过 200 行
- [ ] 门面类对外 API 保持兼容
- [ ] 子服务通过依赖注入获取
- [ ] 现有测试全部通过

## 涉及文件

| 文件路径 | 操作 | 说明 |
|---------|------|------|
| `backend/src/service/document_ingestion_service.py` | 删除 | 原 742 行文件 |
| `backend/src/service/ingestion/__init__.py` | 新增 | 模块入口 |
| `backend/src/service/ingestion/orchestrator.py` | 新增 | IngestionOrchestrator（导入编排，~200 行） |
| `backend/src/service/ingestion/task_state.py` | 新增 | TaskStateManager（任务状态，~100 行） |
| `backend/src/service/ingestion/document_parser.py` | 新增 | DocumentParser（文档解析，~200 行） |
| `backend/src/service/ingestion/pipeline.py` | 新增 | IngestionPipeline（流水线，~150 行） |
| `backend/src/service/ingestion/deduplicator.py` | 新增 | ContentDeduplicator（内容去重，~80 行） |

## 拆分方案

### 职责划分

| 子服务 | 职责 | 原 DocumentIngestionService 方法 |
|--------|------|--------------------------------|
| `IngestionOrchestrator` | 导入流程编排、断点续传 | `ingest_document`, `resume_ingestion` |
| `TaskStateManager` | 任务状态持久化、进度更新 | `_update_task_status`, `_get_task_state` |
| `DocumentParser` | 文档解析、VL 降级、质检 | `_parse_document`, `_validate_quality` |
| `IngestionPipeline` | 分块→元数据→索引流水线 | `_run_pipeline`, `_execute_steps` |
| `ContentDeduplicator` | 内容哈希去重 | `_check_duplicate`, `_calculate_hash` |

### 门面类实现

```python
"""
文档导入门面类

协调各导入子服务，对外提供统一导入 API。
"""

from typing import Optional

from src.service.ingestion.orchestrator import IngestionOrchestrator
from src.service.ingestion.task_state import TaskStateManager
from src.service.ingestion.document_parser import DocumentParser
from src.service.ingestion.pipeline import IngestionPipeline
from src.service.ingestion.deduplicator import ContentDeduplicator


class IngestionFacade:
    """文档导入门面类"""

    def __init__(
        self,
        orchestrator: IngestionOrchestrator,
        task_state: TaskStateManager,
        parser: DocumentParser,
        pipeline: IngestionPipeline,
        deduplicator: ContentDeduplicator,
    ):
        self._orchestrator = orchestrator
        self._task_state = task_state
        self._parser = parser
        self._pipeline = pipeline
        self._deduplicator = deduplicator

    async def ingest(self, file, task_id: str) -> dict:
        """统一文档导入入口"""
        self._task_state.start(task_id)

        if self._deduplicator.is_duplicate(file):
            return self._deduplicator.get_existing_ref(file)

        document = await self._parser.parse(file)
        result = await self._pipeline.run(document)

        self._task_state.complete(task_id, result)
        return result


# 单例
ingestion_facade: Optional[IngestionFacade] = None


def get_ingestion_facade() -> IngestionFacade:
    global ingestion_facade
    if ingestion_facade is None:
        ingestion_facade = IngestionFacade(
            orchestrator=IngestionOrchestrator(),
            task_state=TaskStateManager(),
            parser=DocumentParser(),
            pipeline=IngestionPipeline(),
            deduplicator=ContentDeduplicator(),
        )
    return ingestion_facade
```

## 测试方案

1. 导入流程与拆分前一致
2. 断点续传功能正常
3. 去重逻辑正确
4. 任务状态持久化正确

## 注意事项

- 文档解析涉及多种格式（PDF/EPUB/TXT），需保持兼容
- 任务状态需支持 Redis 持久化
- 去重使用内容哈希，避免重复导入
