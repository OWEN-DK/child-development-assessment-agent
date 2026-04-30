# RAG 评估运行管理问题诊断报告

**生成时间**: 2026-04-30  
**问题描述**: 运行管理中新建运行后，点击评估按钮，运行速度过慢，有无效弹窗，最终输出不出报告

---

## 一、核心问题汇总

### 问题 1: 评估流程断裂 —— 执行与报告生成未衔接

**严重程度**: 🔴 致命

**问题根因**:
1. **前端调用链断裂** (`RunPage.tsx:50-55`):
   - 点击"评估"按钮时，调用 `useTriggerEvaluation()` hook
   - 该 hook 实际调用的是 `POST /api/v1/rag/eval/runs/{id}/evaluate` 接口
   - 但随后打开的 SSE 监听 URL 是 `/api/v1/rag/eval/runs/{id}/stream`

2. **后端接口职责混乱** (`run_controller.py:64-67` vs `metric_controller.py:44-53`):
   - `/runs/{id}/stream` 是 SSE 端点，用于监听**测试运行执行进度**
   - `/runs/{id}/evaluate` 是**指标计算**端点，用于计算已执行完的测试结果的指标
   - 前端将两个接口混用，导致：
     - 点击"评估"时，先触发 `evaluate` 接口（计算指标）
     - 然后监听 `stream` 接口（等待测试执行进度）
     - 但测试根本没有执行，所以 SSE 永远收不到 `complete` 或 `error` 事件

3. **执行流程缺失** (`run_controller.py:30-33`):
   - `create_run` 接口在创建运行后立即调用 `start_run` 启动后台任务
   - 但前端 `handleCreate` 只调用了 `createMutation`，没有处理返回的 `task_id`
   - 也没有打开 SSE 监听窗口，导致用户看不到创建后的执行进度

**代码证据**:
```typescript
// frontend/src/features/rag-eval/pages/RunPage.tsx:50-55
const handleStartEvaluation = useCallback(async (id: string) => {
  await triggerEvalMutation.mutateAsync(id);  // 调用的是 evaluate 接口（计算指标）
  setActiveRunId(id);
  setSseUrl(`/api/v1/rag/eval/runs/${id}/stream`);  // 监听的是执行进度流
  setProgressModalOpen(true);
}, [triggerEvalMutation]);
```

```python
# backend/src/controller/rag_eval/run_controller.py:30-33
async def create_run(self, body: TestRunCreate = Body(...)):
    result = await self._engine.create_run(body)
    task_id = await self._engine.start_run(result.id)  # 创建后立即启动执行
    return APIResponse.success({"run": result.model_dump(mode="json"), "task_id": task_id})
```

---

### 问题 2: SSE 事件格式不匹配导致弹窗无效

**严重程度**: 🟠 严重

**问题根因**:
1. **后端推送格式** (`batch_runner.py:135-145`):
   ```python
   payload = {"type": event_type, "data": data}  # 格式: {type, data}
   ```

2. **前端解析逻辑** (`useSSEProgress.ts:33-46`):
   ```typescript
   const event: SSEEvent = JSON.parse(raw);
   // 期望格式: {type, data}
   ```

3. **但 RagEvalTaskManager 推送格式不同** (`rag_eval_task_manager.py:129-140`):
   ```python
   payload = {"type": event_type, **data}  # 格式: {type, ...data字段平铺}
   ```

4. **前端弹窗展示的字段不存在**:
   - `RunPage.tsx:151-153` 尝试读取 `event.data.progress`
   - 但后端推送的 `case_started` 事件中，进度信息在 `event.data.index` 和 `event.data.total`
   - 需要前端自行计算进度百分比，但当前代码直接使用不存在的 `progress` 字段

**代码证据**:
```typescript
// frontend/src/features/rag-eval/pages/RunPage.tsx:151-153
{event.type === 'progress' && event.data && (
  <Progress percent={Math.round((event.data.progress as number) || 0)} size="small" />
)}
```

```python
# backend/src/service/rag_eval/run/batch_runner.py:66-69
await self._push_event(channel, "case_started", {
    "run_id": run_id,
    "case_id": case.id,
    "query": case.query,
    "index": index,
    "total": total,
})
```

---

### 问题 3: 性能瓶颈 —— 并发配置缺失与执行器未注入依赖

**严重程度**: 🟠 严重

**问题根因**:

1. **并发配置读取失败** (`batch_runner.py:59`):
   ```python
   concurrency = self._get_config_int("rag.eval.run.concurrency", 3)
   ```
   - 默认并发数仅为 3，如果测试集有 50+ 用例，会非常慢
   - 需要检查 MySQL 配置表中是否存在该配置项

2. **执行器缺少 retrieval_fn 和 generation_fn** (`executor.py:26-32`):
   ```python
   async def execute(
       self,
       test_case,
       run_id: str,
       retrieval_fn=None,  # 默认为 None
       generation_fn=None,  # 默认为 None
       timeout_ms: int | None = None,
   ) -> TestRunResultItem:
   ```
   - `batch_runner.py:129-133` 调用时没有传入这两个函数
   - 导致执行器实际上**不执行任何检索和生成操作**
   - 只是空跑一遍，保存一个空结果

3. **超时配置过大** (`executor.py:44`):
   ```python
   timeout_ms = self._get_config_int("rag.eval.run.timeout_ms", 30000)
   ```
   - 默认超时 30 秒，如果配置了 LLM 调用，可能不够
   - 但因为 retrieval_fn 和 generation_fn 为 None，所以实际上不会超时

**代码证据**:
```python
# backend/src/service/rag_eval/run/batch_runner.py:128-133
async def _execute_with_semaphore(self, sem, case, run_id):
    async with sem:
        timeout_ms = self._get_config_int("rag.eval.run.timeout_ms", 30000)
        return await self._executor.execute(
            test_case=case,
            run_id=run_id,
            timeout_ms=timeout_ms,
            # 缺少 retrieval_fn 和 generation_fn！
        )
```

---

### 问题 4: 前端弹窗状态管理混乱

**严重程度**: 🟡 中等

**问题根因**:

1. **SSE 终结事件不匹配** (`useSSEProgress.ts:14-17`):
   ```typescript
   const TERMINAL_EVENTS = new Set(['complete', 'error']);
   ```
   - 但后端推送的事件类型是 `run_completed` 和 `run_failed`
   - 导致 SSE 连接永远不会标记为 `done`
   - 弹窗一直显示"运行中..."

2. **弹窗关闭逻辑缺失**:
   - `RunPage.tsx:139` 弹窗只在用户手动点击关闭时关闭
   - 没有在 SSE 状态变为 `done` 时自动关闭
   - 也没有在 `done` 时自动刷新列表

3. **创建运行后的行为不符合预期**:
   - `create_run` 接口已经启动了后台任务
   - 但前端没有打开进度弹窗
   - 用户需要手动点击"评估"按钮，但此时运行已经在执行中

---

## 四、问题影响链路

```
用户点击"新建运行"
  ↓
后端创建运行记录并立即启动后台任务 (start_run)
  ↓
前端只显示"运行已创建"提示，没有打开进度弹窗 ❌
  ↓
用户看到运行列表中的状态是 "running" 或 "pending"
  ↓
用户点击"评估"按钮
  ↓
前端调用 evaluate 接口（计算指标），但测试还没执行完 ❌
  ↓
前端打开 SSE 监听窗口，等待执行进度事件
  ↓
但执行已经在后台完成了（或正在执行），SSE 事件可能已丢失 ❌
  ↓
弹窗一直显示"运行中..."，因为收不到 complete/error 事件 ❌
  ↓
最终无法输出报告
```

---

### 问题 5: 依赖注入不完整 —— 关键服务未注册

**严重程度**: 🔴 致命

**问题根因**:

1. **`BatchTestRunner` 缺少 RAG 服务注入** (`di_container.py:450-459`):
   ```python
   @provider
   def provide_batch_runner(
       self, test_case_executor: TestCaseExecutor, result_processor: ResultProcessor,
       test_run_repository: TestRunRepository, test_run_result_repository: TestRunResultRepository,
   ) -> BatchTestRunner:
       return BatchTestRunner(
           executor=test_case_executor,
           result_processor=result_processor,
           test_run_repository=test_run_repository,
           test_run_result_repository=test_run_result_repository,
           # 缺少 sse_publisher 和 rag_service！
       )
   ```
   - `BatchTestRunner.__init__` 接收 `sse_publisher` 参数，但 DI 容器没有注入
   - 导致 SSE 推送功能完全失效（`batch_runner.py:137` 检查 `if not channel or not self._sse: return`）

2. **`RunEngineFacade` 缺少 `AsyncTaskManager` 注入** (`di_container.py:470-483`):
   ```python
   @provider
   def provide_run_engine_facade(
       self, test_case_executor: TestCaseExecutor, batch_runner: BatchTestRunner, ...
   ) -> RunEngineFacade:
       return RunEngineFacade(
           executor=test_case_executor,
           batch_runner=batch_runner,
           ...
           # 缺少 async_task_manager 参数！
       )
   ```
   - `RunEngineFacade.__init__` 接收 `async_task_manager` 参数，但 DI 容器没有注入
   - 导致 `start_run` 方法中使用默认创建的 `AsyncTaskManager()` 实例
   - 但该实例可能没有正确配置 Redis 连接或 SSE Publisher

3. **`TaskModule` 没有提供 `AsyncTaskManager` 的 Provider**:
   - `TaskModule` 只提供了 `TaskStateService`
   - `AsyncTaskManager` 是一个类方法为主的工具类，不需要 DI
   - 但 `RagEvalTaskManager` 和 `AsyncTaskManager` 之间的关系不清晰

**影响**: SSE 推送完全失效，前端无法收到任何进度事件

---

### 问题 6: 报告构建器字段不匹配 —— 无法生成报告

**严重程度**: 🔴 致命

**问题根因**:

1. **报告构建器读取不存在的字段** (`builder.py:47`):
   ```python
   metrics_json = run.metrics_json or {}
   ```
   - `TestRun` 模型中**没有 `metrics_json` 字段**
   - 实际字段是 `l1_metrics_json`, `l2_metrics_json`, `l3_metrics_json`
   - 导致 `metrics_json` 始终为 `{}`

2. **报告构建器读取的字段结构不匹配** (`builder.py:48-51`):
   ```python
   l1_json = metrics_json.get("l1", {}) if isinstance(metrics_json, dict) else {}
   l2_json = metrics_json.get("l2", {}) if isinstance(metrics_json, dict) else {}
   l3_json = metrics_json.get("l3", {}) if isinstance(metrics_json, dict) else {}
   ```
   - 期望从 `metrics_json` 中读取 `l1/l2/l3` 子字段
   - 但实际数据直接存储在 `l1_metrics_json`, `l2_metrics_json`, `l3_metrics_json` 中

3. **数据库模型字段与 Schema 字段不一致**:
   - 模型: `l1_metrics_json`, `l2_metrics_json`, `l3_metrics_json`
   - Schema: `l1_metrics_json`, `l2_metrics_json`, `l3_metrics_json`（一致）
   - 但报告构建器期望的是 `metrics_json.l1`, `metrics_json.l2`, `metrics_json.l3`

**影响**: 报告永远无法正确生成，所有指标都为 0 或空

**代码证据**:
```python
# backend/src/models/rag_eval/test_run.py:56-64
l1_metrics_json: Mapped[dict[str, Any] | None] = mapped_column(
    JSON, comment="L1 检索质量指标"
)
l2_metrics_json: Mapped[dict[str, Any] | None] = mapped_column(
    JSON, comment="L2 生成质量指标"
)
l3_metrics_json: Mapped[dict[str, Any] | None] = mapped_column(
    JSON, comment="L3 系统质量指标"
)
```

```python
# backend/src/service/rag_eval/report/builder.py:47-51
metrics_json = run.metrics_json or {}  # 字段不存在！
l1_json = metrics_json.get("l1", {}) if isinstance(metrics_json, dict) else {}
l2_json = metrics_json.get("l2", {}) if isinstance(metrics_json, dict) else {}
l3_json = metrics_json.get("l3", {}) if isinstance(metrics_json, dict) else {}
```

---

### 问题 7: 前端 API 与后端控制器字段名不匹配

**严重程度**: 🟠 严重

**问题根因**:

1. **批量删除接口字段名不一致**:
   - 前端 (`runs.ts:44`): `{ data: { ids } }`
   - 后端 (`run_controller.py:54`): `body.get("run_ids", [])`
   - 字段名 `ids` vs `run_ids` 不匹配

2. **运行对比接口参数名不一致**:
   - 前端 (`runs.ts:60-62`): `params: { run1: runId1, run2: runId2 }`
   - 后端 (`run_controller.py:71-73`): `run_id_1: str = Query(...)`, `run_id_2: str = Query(...)`
   - 参数名 `run1` vs `run_id_1` 不匹配

3. **测试运行结果字段名不一致**:
   - 前端类型 (`types.ts:140`): `case_id: string`
   - 后端 Schema (`test_run.py:81`): `test_case_id: str`
   - 字段名 `case_id` vs `test_case_id` 不匹配

**影响**: 批量删除、运行对比等功能无法正常工作

---

### 问题 8: 快照管理使用文件系统 —— 不适合多实例部署

**严重程度**: 🟡 中等

**问题根因**:

1. **快照存储在本地文件系统** (`snapshot_manager.py:163-166`):
   ```python
   def _get_snapshot_dir(self, snapshot_id: str) -> Path:
       base = Path(__file__).resolve().parent.parent.parent.parent.parent
       return base / "storage" / "snapshots" / snapshot_id
   ```
   - 使用 `shutil.copytree` 复制整个索引目录
   - 多实例部署时，每个实例有独立的文件系统
   - 快照无法在实例间共享

2. **工作目录硬编码** (`snapshot_manager.py:158-161`):
   ```python
   def _get_work_dir(self) -> Path:
       base = Path(__file__).resolve().parent.parent.parent.parent.parent
       return base / "storage" / "rag_eval"
   ```
   - 路径相对于源代码文件，不适合容器化部署
   - 容器重启后快照可能丢失

3. **快照创建时阻塞主线程**:
   - `shutil.copytree` 是同步操作
   - 如果索引目录很大（GB 级别），会阻塞异步事件循环
   - 应该使用后台任务或异步文件操作

**影响**: 多实例部署时快照功能不可用，大索引创建快照时可能超时

---

### 问题 9: 错误处理和异常恢复不完整

**严重程度**: 🟡 中等

**问题根因**:

1. **执行器吞没异常** (`executor.py:69-74`):
   ```python
   except asyncio.TimeoutError:
       error_msg = f"单用例执行超时 ({timeout_ms}ms)"
   except AppException:
       raise
   except Exception as e:
       error_msg = str(e)
   ```
   - 超时和异常只记录 `error_msg`，但没有记录详细堆栈
   - 无法通过日志排查问题根因

2. **批量执行器异常处理不完整** (`batch_runner.py:81-87`):
   ```python
   except Exception as e:
       await self._push_event(channel, "case_failed", {
           "case_id": case.id,
           "query": case.query,
           "error": str(e),
       })
       return None
   ```
   - 异常用例返回 `None`，但聚合结果时没有正确处理
   - `results = await asyncio.gather(*tasks, return_exceptions=True)` 会混入异常对象

3. **SSE 订阅清理不完整** (`sse.py:98-130`):
   - `finally` 块中取消了心跳任务和 Redis 监听任务
   - 但没有清理 `_local_subscribers` 中可能残留的空列表
   - 长时间运行后可能导致内存泄漏

---

### 问题 10: 前端状态管理缺少实时同步

**严重程度**: 🟡 中等

**问题根因**:

1. **运行列表缓存时间过长** (`useTestRuns.ts:16`):
   ```typescript
   staleTime: 30_000,  // 30 秒
   ```
   - 运行状态从 `pending` 变为 `running` 再变为 `completed` 可能只需要几秒
   - 30 秒缓存导致用户看到的列表状态严重滞后

2. **SSE 事件没有触发列表刷新**:
   - `useSSEProgress` hook 只更新 `events` 和 `status`
   - 没有在收到 `run_completed` 事件时触发 `refetch()`
   - 用户需要手动刷新页面才能看到最新状态

3. **创建运行后没有立即优化更新**:
   - `useCreateRun` 的 `onSuccess` 只调用 `invalidateQueries`
   - 没有使用 `setQueryData` 立即将新运行添加到列表
   - 用户需要等待 30 秒缓存过期才能看到新运行

---

## 五、修复建议

### 修复 1: 分离"执行"和"评估"两个操作

**目标**: 明确区分测试执行和指标计算两个阶段

**方案**:
1. 前端新增"执行"按钮，调用 `POST /runs/{id}/execute` 接口
2. "评估"按钮只在运行状态为 `completed` 时可用
3. 创建运行后不自动启动，由用户手动点击"执行"

**代码修改**:
```typescript
// RunPage.tsx - 新增执行按钮
const handleExecute = useCallback(async (id: string) => {
  setActiveRunId(id);
  setSseUrl(`/api/v1/rag/eval/runs/${id}/stream`);
  setProgressModalOpen(true);
  // 调用执行接口（需要后端新增）
  await executeRun(id);
}, []);

// 评估按钮只在 completed 状态时可用
{record.status === 'completed' && (
  <Button size="small" onClick={() => handleStartEvaluation(record.id)}>评估</Button>
)}
```

### 修复 2: 统一 SSE 事件格式

**目标**: 前后端使用统一的事件格式和终结事件类型

**方案**:
1. 后端统一使用 `{type, data}` 格式
2. 终结事件改为 `run_completed` 和 `run_failed`
3. 前端更新 `TERMINAL_EVENTS` 集合

**代码修改**:
```typescript
// useSSEProgress.ts
const TERMINAL_EVENTS = new Set([
  'run_completed',
  'run_failed',
  'complete',
  'error',
]);
```

```python
# batch_runner.py - 统一事件格式
await self._push_event(channel, "run_completed", {
    "run_id": run_id,
    "passed_count": passed,
    "failed_count": failed,
    "total_count": total,
})
```

### 修复 3: 注入检索和生成函数

**目标**: 让执行器真正执行 RAG 检索和 LLM 生成

**方案**:
1. 在 `RunEngineFacade` 或 `BatchTestRunner` 中注入 RAG 服务
2. 构造 `retrieval_fn` 和 `generation_fn`
3. 传递给 `executor.execute()`

**代码修改**:
```python
# batch_runner.py
async def _execute_with_semaphore(self, sem, case, run_id):
    async with sem:
        timeout_ms = self._get_config_int("rag.eval.run.timeout_ms", 30000)
        
        # 构造检索函数
        async def retrieval_fn(query, age, domain):
            return await self._rag_service.search(query, top_k=5)
        
        # 构造生成函数
        async def generation_fn(query, retrieved_ids):
            return await self._llm_service.generate_answer(query, retrieved_ids)
        
        return await self._executor.execute(
            test_case=case,
            run_id=run_id,
            timeout_ms=timeout_ms,
            retrieval_fn=retrieval_fn,
            generation_fn=generation_fn,
        )
```

### 修复 4: 优化并发配置

**目标**: 提高批量测试的执行速度

**方案**:
1. 在 MySQL 配置表中添加 `rag.eval.run.concurrency` 配置
2. 默认值调整为 5-10（根据服务器资源）
3. 前端提供配置页面让用户调整

### 修复 5: 完善依赖注入

**目标**: 确保所有关键服务都正确注入

**方案**:
1. 在 `RagEvalModule` 中为 `BatchTestRunner` 注入 `SSEPublisher`
2. 在 `RagEvalModule` 中为 `RunEngineFacade` 注入 `AsyncTaskManager`
3. 如果需要注入 RAG 服务，添加 `IRetrievalService` 和 `ILlmService` 的 Provider

**代码修改**:
```python
# di_container.py
@singleton
@provider
def provide_batch_runner(
    self, test_case_executor: TestCaseExecutor, result_processor: ResultProcessor,
    test_run_repository: TestRunRepository, test_run_result_repository: TestRunResultRepository,
    sse_publisher: SSEPublisher,  # 新增
) -> BatchTestRunner:
    return BatchTestRunner(
        executor=test_case_executor,
        result_processor=result_processor,
        test_run_repository=test_run_repository,
        test_run_result_repository=test_run_result_repository,
        sse_publisher=sse_publisher,  # 新增
    )

@singleton
@provider
def provide_run_engine_facade(
    self, test_case_executor: TestCaseExecutor, batch_runner: BatchTestRunner, ...
    async_task_manager: AsyncTaskManager,  # 新增
) -> RunEngineFacade:
    return RunEngineFacade(
        executor=test_case_executor,
        batch_runner=batch_runner,
        async_task_manager=async_task_manager,  # 新增
        ...
    )
```

### 修复 6: 修正报告构建器字段读取

**目标**: 让报告构建器正确读取指标数据

**方案**:
1. 修改 `ReportBuilder.build()` 方法，直接从 `run.l1_metrics_json`, `run.l2_metrics_json`, `run.l3_metrics_json` 读取
2. 删除对不存在的 `run.metrics_json` 的引用

**代码修改**:
```python
# builder.py
async def build(self, run_id: str) -> EvalReportData:
    run = await self._run_repo.get_by_id(run_id)
    if run is None:
        raise TestRunNotFoundException(run_id)

    # 直接从扁平字段读取
    l1_json = run.l1_metrics_json or {}
    l2_json = run.l2_metrics_json or {}
    l3_json = run.l3_metrics_json or {}
    diag_json = run.diagnosis_json or {}

    metrics = self._parse_metrics(l1_json, l2_json, l3_json, {
        "overall_score": run.overall_score,
        "weights": {"l1": 0.4, "l2": 0.4, "l3": 0.2}
    })
    ...
```

### 修复 7: 统一前后端字段名

**目标**: 确保前后端使用一致的字段名

**方案**:
1. 前端 API 调用使用后端期望的字段名
2. 或者后端兼容前端的字段名（推荐，因为前端可能有多处调用）

**代码修改**:
```python
# run_controller.py - 批量删除
async def batch_delete_runs(self, body: dict = Body(...)):
    run_ids = body.get("run_ids") or body.get("ids", [])  # 兼容两种字段名
    if not run_ids:
        raise AppException(400, 13016, "run_ids 不能为空", "INVALID_TEST_CASE_FORMAT")
    await self._engine.batch_delete_runs(run_ids)
    return APIResponse.success(None)

# run_controller.py - 运行对比
async def compare_runs(
    self,
    run_id_1: str = Query(..., alias="run1"),  # 使用 alias 兼容前端
    run_id_2: str = Query(..., alias="run2"),
):
    result = await self._engine.compare_runs(run_id_1, run_id_2)
    return APIResponse.success(result.model_dump(mode="json"))
```

### 修复 8: 优化快照管理（长期优化）

**目标**: 支持多实例部署的快照管理

**方案**:
1. 将快照存储从文件系统迁移到对象存储（如 S3、MinIO）
2. 使用异步文件操作或后台任务执行快照创建
3. 快照元数据仍然存储在 MySQL 中

**注意**: 这是长期优化项，不影响当前单实例部署的功能

### 修复 9: 完善错误处理

**目标**: 提高问题排查效率

**方案**:
1. 执行器记录详细异常堆栈
2. 批量执行器正确处理 `asyncio.gather` 返回的异常对象
3. SSE 订阅清理时彻底清理空列表

**代码修改**:
```python
# executor.py
except Exception as e:
    error_msg = str(e)
    logger.error(f"用例执行失败 case_id={test_case.id}, error={e}", exc_info=True)

# batch_runner.py
results = await asyncio.gather(*tasks, return_exceptions=True)
# 过滤异常对象
valid_results = [r for r in results if not isinstance(r, Exception)]
exceptions = [r for r in results if isinstance(r, Exception)]
if exceptions:
    logger.warning(f"批量执行中有 {len(exceptions)} 个用例异常")
```

### 修复 10: 优化前端状态同步

**目标**: 提高前端状态实时性

**方案**:
1. 降低运行列表缓存时间到 5-10 秒
2. SSE 收到 `run_completed` 事件时触发列表刷新
3. 创建运行后立即使用 `setQueryData` 优化更新

**代码修改**:
```typescript
// useTestRuns.ts
export function useTestRuns(filters?: RunFilters) {
  return useQuery({
    queryKey: ['rag-eval', 'runs', filters],
    queryFn: () => runsApi.getRuns(filters),
    staleTime: 10_000,  // 降低到 10 秒
  });
}

// useSSEProgress.ts - 新增回调
export function useSSEProgress(url: string | null, onComplete?: () => void) {
  // ...
  const handleMessage = useCallback((raw: string) => {
    // ...
    if (TERMINAL_EVENTS.has(event.type)) {
      setStatus('done');
      onComplete?.();  // 触发刷新
    }
  }, [onComplete]);
}
```

---

## 六、后续验证步骤

### 核心功能验证（P0 问题修复后）

1. **执行流程验证**:
   - 新建运行后，状态应为 `pending`
   - 点击"执行"按钮，应打开 SSE 弹窗
   - 弹窗应显示 `run_started`, `case_started`, `case_completed` 等事件
   - 执行完成后，状态应变为 `completed`
   - SSE 弹窗应自动关闭或显示"完成"状态

2. **SSE 推送验证**:
   - 检查 `BatchTestRunner` 是否正确接收 `sse_publisher` 参数
   - 检查 SSE 事件格式是否为 `{type, data}`
   - 检查前端 `TERMINAL_EVENTS` 是否包含 `run_completed` 和 `run_failed`
   - 检查弹窗是否能正确显示进度并自动关闭

3. **报告生成验证**:
   - 点击"评估"按钮，应调用 `evaluate` 接口
   - 检查报告构建器是否正确读取 `l1_metrics_json`, `l2_metrics_json`, `l3_metrics_json`
   - 检查生成的报告是否包含正确的指标数据
   - 检查报告是否能正常导出

4. **依赖注入验证**:
   - 检查 DI 容器是否正确注入所有必需的服务
   - 检查 `RunEngineFacade` 是否正确接收 `async_task_manager` 参数
   - 检查 `BatchTestRunner` 是否正确接收 `sse_publisher` 参数

### 功能完整性验证（P1 问题修复后）

5. **API 字段名验证**:
   - 测试批量删除功能，检查是否使用正确的字段名 `run_ids`
   - 测试运行对比功能，检查是否使用正确的参数名 `run_id_1` 和 `run_id_2`
   - 检查测试结果中的字段名是否与前端类型定义一致

6. **前端状态同步验证**:
   - 新建运行后，检查列表是否立即显示新运行
   - 执行过程中，检查列表状态是否实时更新
   - 执行完成后，检查列表是否自动刷新

### 性能验证（P2 问题修复后）

7. **性能验证**:
   - 记录 50 个用例的执行时间
   - 调整并发配置（5/10/20），观察性能变化
   - 检查 LLM 调用是否正常返回
   - 检查 SSE 推送是否流畅，无卡顿

8. **边界测试**:
   - 测试空测试集
   - 测试超大测试集（100+ 用例）
   - 测试执行超时情况
   - 测试 SSE 连接断开重连
   - 测试多实例部署时快照功能

---

**报告结束**
