# 06 - RunEngine 详细设计

## 需求

执行测试运行：将测试用例提交给 RAG 检索管道，收集检索结果和生成答案，汇总为 `test_run_results`。支持单用例执行和批量并发执行，通过 SSE 实时推送进度。

## 当前问题

| 问题 | 位置 | 影响 |
|------|------|------|
| 双执行路径 | `execute_test_case` vs `run_test_case` | 逻辑重复，维护混乱 |
| 4 个文件拼凑 | `test_executor.py`, `test_batch_runner.py`, `test_result_analyzer.py`, `snapshot_service.py` | 职责分散，调用链复杂 |
| SSE 事件格式不统一 | 各处自定义 | 前端解析困难 |
| 快照管理耦合执行 | `snapshot_service.py` 独立但接口不清晰 | 快照恢复不可靠 |
| sync/async 混用 | 多处 | 潜在死锁风险 |
| 无执行超时控制 | 缺失 | 单用例卡死阻塞整批 |

## 引擎架构

```
RunEngineFacade (facade.py, ~120行)
  ├── TestCaseExecutor (executor.py, ~120行)
  ├── BatchTestRunner (batch_runner.py, ~180行)
  ├── ResultProcessor (result_processor.py, ~100行)
  └── SnapshotManager (snapshot_manager.py, ~120行)
```

### 核心设计决策：统一执行路径

**废除双路径**：删除 `execute_test_case` 和 `run_test_case` 两个方法，统一为 `TestCaseExecutor.execute()`。单用例和批量执行共用同一条代码路径。

## 组件设计

### RunEngineFacade

```python
class RunEngineFacade:
    """运行引擎门面"""

    def __init__(
        self,
        executor: TestCaseExecutor,
        batch_runner: BatchTestRunner,
        result_processor: ResultProcessor,
        snapshot_manager: SnapshotManager,
        test_run_repository: TestRunRepository,
        test_run_result_repository: TestRunResultRepository,
        case_engine: CaseEngineFacade,
        config_manager: ConfigManager,
        async_task_manager: AsyncTaskManager,
    ): ...

    async def create_run(self, data: TestRunCreate) -> TestRunRead:
        """创建测试运行记录

        1. 收集所有 test_set_ids 中的用例 + custom_case_ids
        2. 去重合并
        3. 创建 test_runs 记录（status=pending）
        4. 若 snapshot_id 为空且 auto_snapshot=true，自动创建快照
        5. 保存 config_snapshot（当前 RAG 配置快照）
        """

    async def start_run(self, run_id: str) -> str:
        """启动测试运行（后台任务）

        通过 AsyncTaskManager 启动 batch_runner.execute_run
        返回 task_id 供 SSE 监听
        """

    async def execute_single(
        self,
        run_id: str,
        case_id: str,
    ) -> TestRunResultItem:
        """执行单个测试用例（统一执行路径）

        复用 TestCaseExecutor.execute()
        """

    async def get_run(self, run_id: str) -> TestRunRead:
        """获取测试运行详情"""

    async def list_runs(
        self,
        status: str | None = None,
        test_set_id: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> list[TestRunRead]:
        """列出测试运行"""

    async def delete_run(self, run_id: str) -> None:
        """删除测试运行

        running 状态的运行不可删除（抛 RUN_IN_PROGRESS）
        """

    async def batch_delete_runs(self, run_ids: list[str]) -> None:
        """批量删除测试运行"""

    async def compare_runs(self, run_id_1: str, run_id_2: str) -> RunComparison:
        """比较两个测试运行

        委托给 ResultProcessor.compare
        """
```

### TestCaseExecutor

```python
class TestCaseExecutor:
    """单用例执行器——统一执行路径

    所有执行（单用例/批量中的单个）都走这个类。
    """

    def __init__(
        self,
        retrieval_facade: RetrievalFacade,  # RAG 检索管道
        rag_service: RagService,             # RAG 答案生成（已有，位于 `service/rag_service.py`）
        test_run_result_repository: TestRunResultRepository,
        config_manager: ConfigManager,
    ): ...

    async def execute(
        self,
        test_case: TestCaseRead,
        run_id: str,
        timeout_ms: int | None = None,
    ) -> TestRunResultItem:
        """执行单个测试用例

        统一执行路径：
        1. 记录开始时间
        2. 通过 RetrievalFacade 检索 → retrieved_doc_ids, actual_knowledge_ids
        3. 通过 RagService 生成答案 → actual_answer
        4. 计算检索指标：precision, recall, f1, mrr, ndcg, hit_rate_1/3/5
        5. 构建 TestRunResultItem
        6. 保存到 test_run_results
        7. 返回结果

        超时控制：
        - timeout_ms 从 config 读取（默认 30000）
        - 使用 asyncio.wait_for 包装检索+生成
        - 超时抛 AppException(TEST_EXECUTION_TIMEOUT)
        """

    def _calculate_retrieval_metrics(
        self,
        expected_ids: list[str],
        actual_ids: list[str],
        total_retrieved: int,
    ) -> RetrievalMetrics:
        """计算检索指标

        precision = matched / total_retrieved
        recall = matched / len(expected_ids)
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
        mrr = 1 / (第一个匹配的排名) or 0
        ndcg = DCG / ideal_DCG
        hit_rate_1 = matched_in_top_1
        hit_rate_3 = matched_in_top_3
        hit_rate_5 = matched_in_top_5
        """
```

**Schema:**

```python
class RetrievalMetrics(BaseModel):
    """检索指标计算结果"""
    precision: float
    recall: float
    f1: float
    mrr: float
    ndcg: float
    hit_rate_1: float
    hit_rate_3: float
    hit_rate_5: float
    matched_count: int
    expected_count: int
    actual_count: int
```

### BatchTestRunner

```python
class BatchTestRunner:
    """批量测试运行器

    使用 asyncio.Semaphore 控制并发数。
    """

    def __init__(
        self,
        executor: TestCaseExecutor,
        result_processor: ResultProcessor,
        test_run_repository: TestRunRepository,
        case_engine: CaseEngineFacade,
        config_manager: ConfigManager,
        async_task_manager: AsyncTaskManager,
    ): ...

    async def execute_run(self, run_id: str, task_id: str) -> None:
        """执行完整的测试运行

        流程：
        1. 更新 run status → running
        2. SSE: {type: "run_started", data: {run_id, total_cases}}
        3. 获取所有测试用例
        4. 读取并发配置 rag.eval.run.concurrency（默认 3）
        5. 创建 Semaphore(concurrency)
        6. 逐个提交执行：
           for case in cases:
               asyncio.create_task(self._execute_with_semaphore(sem, case, run_id))
        7. 等待所有任务完成
        8. 调用 result_processor.aggregate(run_id) 汇总指标
        9. 更新 run status → completed
        10. SSE: {type: "run_completed", data: {run_id, passed, failed}}

        异常处理：
        - 单用例失败不中断整批，记录 error_message
        - 全批异常（如数据库断连）→ run status = failed
        - SSE: {type: "run_failed", data: {run_id, error}}
        """

    async def _execute_with_semaphore(
        self,
        sem: asyncio.Semaphore,
        case: TestCaseRead,
        run_id: str,
    ) -> TestRunResultItem | None:
        """带信号量控制的单用例执行

        1. async with sem:
        2. SSE: {type: "case_started", data: {run_id, case_id, query}}
        3. executor.execute(case, run_id)
        4. SSE: {type: "case_completed", data: {case_id, passed, metrics}}
        5. 异常时：
           SSE: {type: "case_failed", data: {case_id, error}}
           返回 None
        """
```

### ResultProcessor

```python
class ResultProcessor:
    """结果聚合与运行对比"""

    def __init__(
        self,
        test_run_repository: TestRunRepository,
        test_run_result_repository: TestRunResultRepository,
        orm_mapper: OrmMapper,
    ): ...

    async def aggregate(self, run_id: str) -> None:
        """汇总单次运行结果

        1. 查询所有 test_run_results where run_id
        2. 计算整体指标均值：overall_precision, overall_recall, overall_f1, overall_mrr, overall_ndcg
        3. 统计 passed_test_cases / total_test_cases
        4. 更新 test_runs 记录的扁平指标字段
        5. 记录 completed_at
        """

    async def compare(self, run_id_1: str, run_id_2: str) -> RunComparison:
        """比较两个测试运行

        1. 验证两个 run_id 存在且已完成
        2. 计算每个指标的 delta = run_2 - run_1
        3. 识别改进/退化的指标
        4. 找出共同的坏案、新增的坏案、修复的坏案
        5. 返回 RunComparison
        """

    async def get_bad_cases(self, run_id: str) -> list[TestRunResultItem]:
        """获取坏案列表（未通过的用例）"""
```

### SnapshotManager

```python
class SnapshotManager:
    """知识库快照管理

    通过 IndexManagerService（已有基础设施，位于 `service/index_manager/facade.py`，
    实现 IIndexManager 接口）创建/恢复向量库快照。
    现有快照机制通过文件系统复制 index 目录和 document_store.json 实现。
    """

    def __init__(
        self,
        snapshot_repository: SnapshotRepository,
        index_manager: IndexManagerService,
        config_manager: ConfigManager,
    ): ...

    async def create_snapshot(
        self,
        name: str | None = None,
        description: str = "",
    ) -> SnapshotRead:
        """创建快照

        1. 调用 IndexManagerService 获取当前向量库状态（index 路径、document_store）
        2. 通过文件系统复制 index 目录和 document_store.json 到快照存储路径
        3. 记录 document_count, chunk_count, vector_store_path
        4. 保存 config_snapshot（当前 RAG 配置）
        5. 持久化到 knowledge_snapshots 表
        """

    async def restore_snapshot(self, snapshot_id: str) -> None:
        """恢复快照

        1. 验证 snapshot 存在
        2. 先创建当前索引的备份（防止恢复失败丢失数据）
        3. 通过文件系统复制快照的 index 目录和 document_store.json 回工作目录
        4. 调用 IndexManagerService 重新初始化索引
        5. 恢复失败抛 AppException(SNAPSHOT_RESTORE_FAILED)，并尝试从备份恢复
        """

    async def list_snapshots(self) -> list[SnapshotRead]:
        """列出所有快照"""

    async def get_snapshot(self, snapshot_id: str) -> SnapshotRead:
        """获取快照详情，不存在抛 AppException(SNAPSHOT_NOT_FOUND)"""
```

## SSE 事件

| 事件类型 | 数据格式 | 说明 |
|----------|----------|------|
| `run_started` | `{run_id, total_cases, snapshot_id}` | 运行开始 |
| `case_started` | `{run_id, case_id, query, index, total}` | 用例开始执行 |
| `case_completed` | `{case_id, passed, precision, recall, execution_time_ms}` | 用例执行完成 |
| `case_failed` | `{case_id, query, error}` | 用例执行失败 |
| `run_completed` | `{run_id, passed_count, failed_count, total_count, duration_ms}` | 运行完成 |
| `run_failed` | `{run_id, error}` | 运行整体失败 |

所有事件统一格式：`{type: str, data: dict}`

## 配置 Key

| Key | 类型 | 默认值 | 说明 |
|-----|------|--------|------|
| `rag.eval.run.concurrency` | int | 3 | 批量执行并发数 |
| `rag.eval.run.timeout_ms` | int | 30000 | 单用例执行超时（毫秒） |
| `rag.eval.run.auto_snapshot` | bool | true | 创建运行时是否自动创建快照 |

## 错误码

| 数字码 | 错误码 | HTTP | 触发场景 |
|--------|--------|------|----------|
| 13004 | `TEST_RUN_NOT_FOUND` | 404 | 运行 ID 不存在 |
| 13005 | `SNAPSHOT_NOT_FOUND` | 404 | 快照 ID 不存在 |
| 13010 | `SNAPSHOT_RESTORE_FAILED` | 500 | 快照恢复失败 |
| 13012 | `TEST_EXECUTION_TIMEOUT` | 408 | 单用例执行超时 |
| 13013 | `TEST_EXECUTION_FAILED` | 500 | 执行内部错误 |
| 13019 | `TEST_SET_EMPTY` | 400 | 测试集无用例 |
| 13020 | `RUN_IN_PROGRESS` | 409 | 删除运行中的记录 |

## 数据流

```
TestRunCreate
  │
  ▼
RunEngineFacade.create_run()
  ├── 收集用例 ID（test_set_ids + custom_case_ids）
  ├── auto_snapshot? → SnapshotManager.create_snapshot()
  ├── 保存 config_snapshot
  └── 创建 test_runs 记录 (status=pending)
  │
  ▼
RunEngineFacade.start_run() → AsyncTaskManager → BatchTestRunner.execute_run()
  │
  ├── Semaphore(concurrency)
  │   └── TestCaseExecutor.execute(case, run_id)
  │       ├── RetrievalFacade.search(query, age, domain) → 检索结果
  │       ├── RagService.generate_answer(query, contexts) → actual_answer
  │       ├── _calculate_retrieval_metrics() → RetrievalMetrics
  │       └── 保存 test_run_results
  │
  ▼
ResultProcessor.aggregate(run_id)
  ├── 计算整体指标均值
  ├── 更新 test_runs 扁平字段
  └── SSE: run_completed
```

## 验收标准

1. `facade.py` ≤ 120 行，`executor.py` ≤ 120 行，`batch_runner.py` ≤ 180 行，`result_processor.py` ≤ 100 行，`snapshot_manager.py` ≤ 120 行
2. **统一执行路径**：`TestCaseExecutor.execute()` 是唯一执行入口，无 `execute_test_case` / `run_test_case` 双路径
3. SSE 事件统一为 `{type, data}` 格式，6 种事件类型完整
4. `BatchTestRunner` 使用 `asyncio.Semaphore` 控制并发，从 `rag.eval.run.concurrency` 读取
5. 单用例超时通过 `asyncio.wait_for` 实现，超时抛 `AppException(TEST_EXECUTION_TIMEOUT)`
6. 单用例失败不中断整批——异常被捕获并推送 `case_failed` SSE 事件
7. 后台任务异常不抛出未捕获异常（防止 `Task exception was never retrieved`）
8. SSE 结果推送使用 `jsonable_encoder` 处理，不直接传 Pydantic/ORM 模型
9. `SnapshotManager` 通过 `IndexManagerService`（`service/index_manager/facade.py`）操作向量库，不直接操作 Chroma
10. `ResultProcessor.compare` 输出完整的 `RunComparison`，包含坏案对比
11. `auto_snapshot=true` 时自动创建快照并关联到 run
12. 所有配置通过 `ConfigManager` 读取，无硬编码
13. `RunEngineFacade` 通过 `RagEvalModule` DI 注入
14. 检索指标计算结果使用 `jsonable_encoder` 后写入 `test_run_results`
