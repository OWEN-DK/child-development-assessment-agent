# RAG 评估：运行与报告合并方案

## 1. 问题分析

当前 RAG 评估的"运行"和"报告生成"是两步独立操作：

1. 用户点击"执行"或"重新评估" → 后台运行测试用例
2. 运行完成后，用户需要**手动点击"生成报告"** → 后台生成报告

**用户期望**：点击"执行/重新评估"后，自动完成"运行 → 指标计算 → 报告生成"全链路，无需手动触发报告生成。

## 2. 现状分析（已确认事实）

### 2.1 后端已具备自动流水线

`RagEvalOrchestrator.post_run_pipeline()` 已经作为 `BatchTestRunner._on_complete` 回调存在，运行完成后自动执行：

```
运行完成 → post_run_pipeline(run_id)
  ├── 步骤 1: 双轨评估（指标计算 + 六层诊断）
  └── 步骤 2: 报告生成（build → render → save）
```

**关键代码路径**：
- [batch_runner.py:214-218](backend/src/service/rag_eval/run/batch_runner.py#L214-L218) — `on_complete` 回调触发
- [orchestrator.py:71-113](backend/src/service/rag_eval/orchestrator.py#L71-L113) — `post_run_pipeline` 实现
- [di_container.py:639](backend/src/core/di_container.py#L639) — 延迟绑定 `on_complete`

### 2.2 后端报告生成不推送 SSE 事件

`post_run_pipeline` 调用的是 `ReportEngineFacade.generate_report()`（同步版本），该方法**不推送 SSE 事件**。而带有 SSE 推送的 `start_generate_report()` 是独立的异步任务，使用不同的 task_type (`report_generation`) 和 SSE channel。

因此前端在运行完成后看不到报告生成进度。

### 2.3 前端按钮分离

[RunPage.tsx:184-205](frontend/src/features/rag-eval/pages/RunPage.tsx#L184-L205) 中，`completed` 状态下有两个独立按钮：
- "重新评估" → 重新运行
- "生成报告" → 手动触发报告生成

### 2.4 SSE 通道

- 运行进度：`test_run:{run_id}`（由 `BatchTestRunner._push_event` 推送）
- 报告生成进度：`report_generation:{task_id}`（由 `TaskSsePublisher` 推送）

两个通道独立，前端分别监听。

## 3. 方案设计

### 3.1 核心思路

**统一 SSE 通道**：将报告生成的进度事件也推送到 `test_run:{run_id}` 通道，前端只需监听一个 SSE 连接即可获得"运行 → 指标 → 报告"全链路进度。

### 3.2 后端改动

#### 3.2.1 修改 `post_run_pipeline` 推送 SSE 事件

**文件**：`backend/src/service/rag_eval/orchestrator.py`

在 `post_run_pipeline` 中增加 SSE 事件推送，复用 `BatchTestRunner._push_event` 的通道 `test_run:{run_id}`：

```python
async def post_run_pipeline(self, run_id: str) -> None:
    channel = f"test_run:{run_id}"
    sse = ...  # 通过构造函数注入 SSEPublisher

    # 步骤 1：双轨评估
    await self._push(channel, "metrics_computing", {"run_id": run_id})
    # ... 现有指标计算逻辑 ...
    await self._push(channel, "metrics_done", {"run_id": run_id})

    # 步骤 2：报告生成
    await self._push(channel, "report_generating", {"run_id": run_id, "stage": "building"})
    # ... build ...
    await self._push(channel, "report_generating", {"run_id": run_id, "stage": "rendering"})
    # ... render ...
    await self._push(channel, "report_generating", {"run_id": run_id, "stage": "saving"})
    # ... save ...
    await self._push(channel, "report_completed", {"run_id": run_id, "report_id": rid})
```

新增 SSE 事件类型（复用 `test_run:{run_id}` 通道）：

| 事件 | 含义 | 数据 |
|------|------|------|
| `metrics_computing` | 开始计算指标 | `{run_id}` |
| `metrics_done` | 指标计算完成 | `{run_id}` |
| `report_generating` | 报告生成中 | `{run_id, stage}` |
| `report_completed` | 报告生成完成 | `{run_id, report_id}` |
| `report_failed` | 报告生成失败 | `{run_id, error}` |

#### 3.2.2 注入 SSEPublisher 到 Orchestrator

**文件**：`backend/src/core/di_container.py`

在 `provide_rag_eval_orchestrator` 中将 `SSEPublisher` 注入到 `RagEvalOrchestrator`。

#### 3.2.3 保留独立的报告生成 API

`POST /api/v1/rag/eval/reports`（`start_generate_report`）保留不动，作为以下场景的兜底：
- 旧运行（已完成但没有报告）需要手动生成
- 报告生成失败后需要重试

### 3.3 前端改动

#### 3.3.1 扩展 SSE 事件监听

**文件**：`frontend/src/features/rag-eval/pages/RunPage.tsx`

在 `startSSE` 的 `onMessage` 回调中增加对报告生成事件的处理：

```typescript
// 现有：run_started, case_completed, case_failed 等
// 新增：
if (event.type === 'metrics_computing') { /* 显示"计算指标中..." */ }
if (event.type === 'report_generating') { /* 显示"生成报告: {stage}..." */ }
if (event.type === 'report_completed') { /* 刷新列表，显示报告链接 */ }
if (event.type === 'report_failed') { /* 显示错误提示 */ }
```

将 `metrics_computing`, `report_generating`, `report_completed`, `report_failed` 加入 `TERMINAL_EVENTS` 或单独处理。

#### 3.3.2 修改按钮逻辑

**文件**：`frontend/src/features/rag-eval/pages/RunPage.tsx`

`completed` 状态下的按钮从：
```
[重新评估] [生成报告]
```
改为：
```
[重新评估] [查看报告]（如果有报告）
```

- 移除"生成报告"按钮（运行已自动生成报告）
- 新增"查看报告"按钮，点击跳转到报告详情页
- 运行进度区域增加报告生成阶段的进度显示

#### 3.3.3 报告生成进度展示

运行进度从原来的"用例执行进度"扩展为"全链路进度"：

```
[████████████████████░░░░░░░░] 20/25 用例
→ 执行完成 → 计算指标中...
→ 指标完成 → 生成报告: building...
→ 生成报告: rendering...
→ 报告已生成 [查看报告]
```

## 4. 涉及文件清单

| 文件 | 改动类型 | 说明 |
|------|---------|------|
| `backend/src/service/rag_eval/orchestrator.py` | 修改 | `post_run_pipeline` 增加 SSE 事件推送 |
| `backend/src/core/di_container.py` | 修改 | 注入 SSEPublisher 到 Orchestrator |
| `frontend/src/features/rag-eval/pages/RunPage.tsx` | 修改 | 扩展 SSE 监听 + 按钮逻辑调整 |

## 5. 不改动的部分

- `ReportEngineFacade` — 保留 `generate_report` 和 `start_generate_report` 两个入口
- `BatchTestRunner` — 无需修改，`on_complete` 回调机制已就绪
- 报告 API 端点 — 保留，作为兜底手动触发入口
- `ReportPage.tsx` / `ReportDetailPage.tsx` — 不涉及

## 6. 风险与兜底

| 风险 | 应对 |
|------|------|
| 报告生成失败（指标计算异常等） | `post_run_pipeline` 已有独立 catch，不影响运行结果；前端显示失败提示，保留"生成报告"按钮作为重试入口 |
| SSE 连接断开 | 前端 `createSSEConnection` 已有重连机制；运行状态持久化在 DB，刷新页面可恢复 |
| 旧运行无报告 | 保留"生成报告"按钮仅对无报告的旧 completed 运行显示 |

## 7. 验收标准

1. 点击"执行"后，用例执行完毕自动进入指标计算和报告生成，前端全程显示进度
2. 点击"重新评估"后，同上
3. 运行完成后，表格中显示"查看报告"按钮（替代原来的"生成报告"）
4. 旧运行（无报告）仍可手动点击"生成报告"
5. 报告生成失败时，前端显示错误提示，不影响运行状态
