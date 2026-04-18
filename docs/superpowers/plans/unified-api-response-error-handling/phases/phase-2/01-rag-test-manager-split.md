# Phase 2-1: RagTestManager 拆分

> **需求来源**: spec 文档 `unified-api-response-and-error-handling.md` 中 `3.3.1` 节
> **所属 Phase**: Phase 2

## 需求定义

将 `RagTestManager`（1875 行）按单一职责拆分为 8 个子服务 + 1 个门面类。

## 验收标准

- [ ] 单类不超过 200 行
- [ ] 门面类对外 API 保持兼容
- [ ] 子服务通过依赖注入获取
- [ ] 现有测试全部通过

## 涉及文件

| 文件路径 | 操作 | 说明 |
|---------|------|------|
| `backend/src/service/rag_test_manager.py` | 删除 | 原 1875 行文件 |
| `backend/src/service/rag_test/__init__.py` | 新增 | 模块入口 |
| `backend/src/service/rag_test/facade.py` | 新增 | RagTestFacade（门面，~150 行） |
| `backend/src/service/rag_test/test_run_executor.py` | 新增 | TestRunExecutor（测试运行/批量并发，~350 行） |
| `backend/src/service/rag_test/test_case_repo.py` | 新增 | TestCaseRepository（用例 CRUD，~300 行） |
| `backend/src/service/rag_test/test_set_manager.py` | 新增 | TestSetManager（测试集 CRUD，~250 行） |
| `backend/src/service/rag_test/draft_generator.py` | 新增 | DraftGenerator（LLM 草稿生成，~350 行） |
| `backend/src/service/rag_test/snapshot_manager.py` | 新增 | SnapshotManager（知识库快照，~200 行） |
| `backend/src/service/rag_test/metrics_calculator.py` | 新增 | TestMetricsCalculator（指标计算，~200 行） |
| `backend/src/service/rag_test/source_doc_manager.py` | 新增 | SourceDocumentManager（源文档管理，~150 行） |

## 拆分方案

### 职责划分

| 子服务 | 职责 | 原 RagTestManager 方法 |
|--------|------|----------------------|
| `TestRunExecutor` | 测试运行、批量并发、分布式锁、SSE 推送 | `run_test_case`, `execute_batch`, `run_test_set` |
| `TestCaseRepository` | 用例 CRUD、批量导入、预览 | `create_test_case`, `update_test_case`, `delete_test_case`, `batch_import` |
| `TestSetManager` | 测试集 CRUD、用例关联、导出 | `create_test_set`, `add_cases_to_set`, `export_test_set` |
| `DraftGenerator` | LLM 草稿生成、审核、导入 | `generate_drafts`, `review_draft`, `import_drafts` |
| `SnapshotManager` | 知识库快照创建、恢复、列表 | `create_snapshot`, `restore_snapshot`, `list_snapshots` |
| `TestMetricsCalculator` | 指标计算、聚合、对比 | `calculate_metrics`, `aggregate_results`, `compare_runs` |
| `SourceDocumentManager` | 源文档上传、删除、列表 | `upload_source_doc`, `delete_source_doc`, `list_source_docs` |
| `RagTestFacade` | 协调各子服务，对外提供统一 API | 所有公开方法 |

### 门面类实现

```python
"""
RAG 测试门面类

协调各子服务，对外提供统一 API。
内部不实现具体业务逻辑，仅转发调用。
"""

from typing import Optional

from src.service.rag_test.test_run_executor import TestRunExecutor
from src.service.rag_test.test_case_repo import TestCaseRepository
from src.service.rag_test.test_set_manager import TestSetManager
from src.service.rag_test.draft_generator import DraftGenerator
from src.service.rag_test.snapshot_manager import SnapshotManager
from src.service.rag_test.metrics_calculator import TestMetricsCalculator
from src.service.rag_test.source_doc_manager import SourceDocumentManager


class RagTestFacade:
    """RAG 测试门面类，协调各子服务"""

    def __init__(
        self,
        executor: TestRunExecutor,
        repo: TestCaseRepository,
        set_manager: TestSetManager,
        draft_gen: DraftGenerator,
        snapshot_mgr: SnapshotManager,
        metrics_calc: TestMetricsCalculator,
        source_doc_mgr: SourceDocumentManager,
    ):
        self._executor = executor
        self._repo = repo
        self._set_manager = set_manager
        self._draft_gen = draft_gen
        self._snapshot_mgr = snapshot_mgr
        self._metrics_calc = metrics_calc
        self._source_doc_mgr = source_doc_mgr

    # === 测试运行 ===
    async def run_test_case(self, case_id: str, run_id: str) -> dict:
        return await self._executor.run_test_case(case_id, run_id)

    async def run_test_set(self, test_set_id: str, run_id: str) -> dict:
        return await self._executor.run_test_set(test_set_id, run_id)

    # === 用例 CRUD ===
    async def create_test_case(self, data: dict) -> dict:
        return await self._repo.create(data)

    async def update_test_case(self, case_id: str, data: dict) -> dict:
        return await self._repo.update(case_id, data)

    async def delete_test_case(self, case_id: str) -> bool:
        return await self._repo.delete(case_id)

    # === 测试集管理 ===
    async def create_test_set(self, data: dict) -> dict:
        return await self._set_manager.create(data)

    async def add_cases_to_set(self, set_id: str, case_ids: list[str]) -> dict:
        return await self._set_manager.add_cases(set_id, case_ids)

    # === 草稿管理 ===
    async def generate_drafts(self, params: dict) -> dict:
        return await self._draft_gen.generate(params)

    # === 快照管理 ===
    async def create_snapshot(self, name: str) -> dict:
        return await self._snapshot_mgr.create(name)

    # === 指标计算 ===
    async def calculate_metrics(self, run_id: str) -> dict:
        return await self._metrics_calc.calculate(run_id)

    # === 源文档管理 ===
    async def upload_source_doc(self, file, name: str) -> dict:
        return await self._source_doc_mgr.upload(file, name)


# 单例
rag_test_facade: Optional[RagTestFacade] = None


def get_rag_test_facade() -> RagTestFacade:
    global rag_test_facade
    if rag_test_facade is None:
        rag_test_facade = RagTestFacade(
            executor=TestRunExecutor(),
            repo=TestCaseRepository(),
            set_manager=TestSetManager(),
            draft_gen=DraftGenerator(),
            snapshot_mgr=SnapshotManager(),
            metrics_calc=TestMetricsCalculator(),
            source_doc_mgr=SourceDocumentManager(),
        )
    return rag_test_facade
```

## 测试方案

1. 门面类转发调用正确
2. 各子服务单元测试通过
3. 集成测试：完整测试流程正常
4. 性能测试：并发运行无退化

## 注意事项

- 拆分后保持现有公开 API 不变，Controller 层无感知
- 子服务之间不直接依赖，通过门面协调
- 依赖注入优先使用 DI 容器，避免全局单例
