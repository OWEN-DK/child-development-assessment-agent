# RAG 评估运行页面缺陷分析

**日期**：2026-05-07
**范围**：RunPage.tsx + 后端运行/报告生成链路

---

## 缺陷清单

| # | 现象 | 根因 | 严重度 |
|---|------|------|--------|
| 1 | 点击"重新生成"/"开始运行"后，耗时未清空 | 后端未清除 `completed_at`；前端 mutation 后未立即 refetch | 中 |
| 2 | 点击"查看进度"没反应 | 点击无任何视觉反馈（无 loading/message），SSE 连接是异步的，用户看不到变化 | 低 |
| 3 | 完成后"通过/总数"未更新 | 前端数据未刷新（与 Bug4 同源） | 高 |
| 4 | 报告没有生成（报告列表页无数据） | `RagEvalOrchestrator` 未被 DI 实例化，`post_run_pipeline` 回调从未执行 | **P0** |

---

## Bug 4（P0）：报告没有生成 — 深度分析

### 现象

运行完成后：
- 报告列表页无数据
- "通过/总数"、"综合得分"未更新
- 前端无"查看报告"按钮

### 根因：RagEvalOrchestrator 从未被 DI 容器实例化

#### 依赖链追踪

`injector` 库的 `@singleton @provider` 仅在**被其他 provider 显式依赖**时才实例化。

**实际依赖图**：

```
provide_rag_eval_orchestrator
  ├─ 依赖: draft_engine_facade, case_engine_facade, run_engine_facade,
  │        metric_engine_facade, report_engine_facade, tuning_engine_facade,
  │        batch_runner
  └─ 返回: RagEvalOrchestrator
           ↓ 内部副作用
           batch_runner._on_complete = orchestrator.post_run_pipeline

provide_controller_registry
  └─ 依赖: 7 个子 controller（draft, case, run, metric, report, tuning, snapshot）
      → 不依赖 RagEvalOrchestrator ← 问题所在
```

**没有任何组件将 `RagEvalOrchestrator` 作为依赖**，因此：

1. `provide_rag_eval_orchestrator` **从未被 injector 调用**
2. `batch_runner._on_complete` 始终为 `None`
3. 运行完成后的回调判断 `if not is_cancelled and self._on_complete` 为 `False`
4. `post_run_pipeline` **从未执行**

#### 关键代码位置

| 文件 | 行号 | 说明 |
|------|------|------|
| `backend/src/core/di_container.py` | 625-642 | `provide_rag_eval_orchestrator` 定义，但无消费者 |
| `backend/src/core/di_container.py` | 641 | `batch_runner._on_complete = orchestrator.post_run_pipeline`（未执行） |
| `backend/src/core/di_container.py` | 685-698 | `provide_controller_registry` 不接收 orchestrator |
| `backend/src/service/rag_eval/run/batch_runner.py` | 219-223 | `on_complete` 回调调用点，因 `_on_complete=None` 被跳过 |

#### 影响链

```
post_run_pipeline 未执行
  → 指标未计算（overall_score、l1/l2/l3_metrics_json 为空）
  → save_evaluation 未调用
  → 报告未生成（reports 表无记录）
  → report_completed SSE 事件未推送
  → 前端 reportIdMap 为空，不显示"查看报告"
  → 前端 refetch 拿到的数据缺少 overall_score 和 passed_test_cases 更新
```

---

## Bug 1：耗时未清空

### 现象

点击"重新评估"后，耗时列仍显示上次运行的时间。

### 根因

**后端**：`batch_runner._execute_run_inner`（line 119-123）重新运行时更新了 `status` 和 `started_at`，但**未清除 `completed_at`**：

```python
await self._run_repo.update(run_id, {
    "status": "running",
    "started_at": datetime.now(timezone.utc),
    "total_test_cases": len(test_cases),
    # 缺少: "completed_at": None
})
```

**前端**：`handleStartEvaluation`（line 136-143）执行成功后**未立即 refetch**，表格显示旧数据：

```tsx
const handleStartEvaluation = useCallback(async (id, status) => {
    await executeMutation.mutateAsync(id);
    startSSE(id);
    // 缺少: refetch() 或等待 invalidateQueries 生效
}, [startSSE, executeMutation]);
```

耗时计算逻辑（line 193-196）：

```tsx
const end = r.completed_at ? new Date(r.completed_at).getTime() : Date.now();
```

旧 `completed_at` 残留 → 耗时显示旧值。

---

## Bug 2：查看进度没反应

### 现象

running 状态下点击"查看进度"，页面无任何变化。

### 根因

`handleStartEvaluation` 中，running 状态分支只调用 `startSSE`，**无任何视觉反馈**：

```tsx
if (status === 'completed' || status === 'pending') {
    await executeMutation.mutateAsync(id);  // 有 loading 状态
    startSSE(id);
} else {
    startSSE(id);  // 无 loading、无 message、无任何 UI 反馈
}
```

SSE 连接是异步的（fetch + ReadableStream），用户点击后看不到任何变化。

---

## Bug 3：通过/总数未更新

### 现象

运行完成后，表格中"通过/总数"列仍显示旧值（如 `0/0` 或上次的值）。

### 根因

与 Bug4 同源：`post_run_pipeline` 未执行，`aggregate` 写入的 `passed_test_cases` 和 `total_test_cases` 虽然在 DB 中已更新，但前端 `refetch` 可能因 `staleTime: 10_000`（10 秒缓存）返回旧数据。

此外，即使 `refetch` 拉到了 `passed_test_cases`，`overall_score` 仍为空（指标未计算），导致综合得分列也显示 `-`。

---

## 修复方向

### Bug 4 修复（P0）

将 `RagEvalOrchestrator` 注入到已有的 DI 依赖链中，确保被实例化：

```python
# di_container.py - 方案：注入到 controller_registry
@singleton
@provider
def provide_controller_registry(
    self, draft_controller, case_controller, run_controller,
    metric_controller, report_controller, tuning_controller,
    snapshot_controller,
    rag_eval_orchestrator: RagEvalOrchestrator,  # 新增依赖，触发实例化
) -> RagEvalControllerRegistry:
    return RagEvalControllerRegistry(...)
```

或更轻量的方案：在 `provide_batch_runner` 中直接接收 orchestrator 的依赖，避免循环依赖。

### Bug 1 修复

1. 后端 `batch_runner._execute_run_inner` 补充清除 `completed_at` 和 `passed_test_cases`
2. 前端 `handleStartEvaluation` 在 mutation 成功后立即 refetch

### Bug 2 修复

running 状态点击"查看进度"时添加 `message.info('正在连接进度...')` 或按钮 loading 状态。

---

## 验收标准

1. 点击"执行"后，运行完成自动生成报告，报告列表页可见
2. 点击"重新评估"后，耗时清空，状态变为 running，通过/总数重置
3. 运行完成后，通过/总数和综合得分正确更新
4. running 状态点击"查看进度"有视觉反馈
