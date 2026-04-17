# 01 - SSE 事件定义 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 01 - SSE 事件定义

**Architecture:** 参考下方原文档的实现方案和数据模型

**Tech Stack:** Python, FastAPI, TypeScript, React

---

### Task 1: 实现核心逻辑与测试

**Files:**
- Test: `tests/test_placeholder.py`

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

> **需求来源**: spec 文档 `03-sse-workflow.md` 中 `3.5.1 SSE 事件定义` 节
> **所属 Phase**: Phase 2

## 事件总览

本文件定义 RAG 评估工作流中全部 10 种 SSE 事件类型。所有事件通过 `SSEPublisher.publish()` 发布，消息格式统一为 JSON 对象，必须包含 `type` 字段标识事件类型。

> **注意**：spec 定义 10 种事件（9 种业务事件 + 1 种系统事件 heartbeat）。`export_failed` 不是独立事件类型，而是导出失败时的错误处理场景，其推送逻辑与 `export_ready` 共用同一独立 SSE 通道 `/api/sse/exports`。前端需同时处理 `export_ready` 和 `export_failed` 两种消息类型。

## 事件清单

| 序号 | 事件类型 | 触发时机 | 数据字段 (spec 定义) | 说明 |
|------|----------|----------|---------------------|------|
| 1 | `run_started` | 测试开始 | `run_id`, `test_set_id`, `total_cases`, `config_version` | 通知前端运行已启动 |
| 2 | `progress` | 每完成一个用例 | `run_id`, `current_case`, `total_cases`, `current_query`, `elapsed_seconds` | 推送当前进度 |
| 3 | `case_result` | 单个用例完成 | `run_id`, `case_id`, `query`, `hit_at_1`, `hit_at_3`, `hit_at_5`, `matched_doc_ids`, `matched_doc_scores`, `status` | 推送单用例命中结果 |
| 4 | `test_completed` | 所有用例执行完毕 | `run_id`, `total_cases`, `passed_cases`, `overall_metrics` | 推送集合指标汇总 |
| 5 | `validation_started` | 校验开始 | `run_id`, `layer` (1-6) | 通知校验阶段启动 |
| 6 | `validation_completed` | 单层校验完成 | `run_id`, `layer`, `duration_ms`, `suggestion_count` | 推送单层校验结果 |
| 7 | `report_ready` | 校验全部完成且报告已生成 | `run_id`, `report_id`, `overall_metrics`, `total_duration_seconds`, `validation_summary` | 通知报告可访问 |
| 8 | `run_failed` | 测试异常中断 | `run_id`, `error_code`, `error_message`, `failed_at_case_id` | 推送错误信息 |
| 9 | `heartbeat` | 每 15 秒定时 | `run_id`, `timestamp` (ISO 8601) | 心跳保活，系统级事件 |
| 10 | `export_ready` | PDF 导出任务完成 | `task_id`, `report_id`, `download_url`, `file_size_bytes` | 推送下载链接（独立通道） |

## 事件 Payload 格式

### 1. run_started
```json
{
  "type": "run_started",
  "run_id": "uuid-string",
  "test_set_id": "uuid-string",
  "total_cases": 50,
  "config_version": "v2.3",
  "timestamp": "2026-04-17T10:00:00Z"
}
```

> **注意**：spec 定义字段名为 `config_version`（版本号字符串，如 "v2.3"），非 `config_version_id`。

### 2. progress
```json
{
  "type": "progress",
  "run_id": "uuid-string",
  "current_case": 15,
  "total_cases": 50,
  "current_query": "什么是感统训练",
  "elapsed_seconds": 90,
  "timestamp": "2026-04-17T10:01:30Z"
}
```

> **注意**：严格按照 spec 定义，字段名为 `current_case`（非 `current`）、`total_cases`（非 `total`），新增 `current_query` 和 `elapsed_seconds`。

### 3. case_result
```json
{
  "type": "case_result",
  "run_id": "uuid-string",
  "case_id": "uuid-string",
  "query": "3岁儿童大肌肉发展迟缓的表现",
  "hit_at_1": true,
  "hit_at_3": true,
  "hit_at_5": true,
  "matched_doc_ids": ["doc-1", "doc-2", "doc-3"],
  "matched_doc_scores": [0.85, 0.72, 0.68],
  "status": "passed",
  "timestamp": "2026-04-17T10:01:31Z"
}
```

> **注意**：严格按照 spec 定义，`case_result` 不包含 `hit_rank`、`retrieved_doc_ids`、`expected_doc_ids`、`precision`、`recall`、`score`、`latency_ms` 字段。集合指标仅在 `test_completed` 中返回。

### 4. test_completed
```json
{
  "type": "test_completed",
  "run_id": "uuid-string",
  "total_cases": 50,
  "passed_cases": 42,
  "overall_metrics": {
    "precision": 0.72,
    "recall": 0.86,
    "f1": 0.78,
    "mrr": 0.71,
    "ndcg": 0.79
  },
  "timestamp": "2026-04-17T10:03:00Z"
}
```

> **注意**：严格按照 spec 定义，指标字段名为 `overall_metrics`，内部使用简化的 key（`precision`/`recall`/`f1`/`mrr`/`ndcg`），不包含 `duration_seconds`、`failed_cases`、各@K细分指标。

### 5. validation_started
```json
{
  "type": "validation_started",
  "run_id": "uuid-string",
  "layer": 1,
  "timestamp": "2026-04-17T10:03:01Z"
}
```

> **注意**：spec 定义 `validation_started` 每层校验开始时各发送一次，包含 `layer` 字段（1-6）。Layer 6 仅在手动触发时发送。

### 6. validation_completed
```json
{
  "type": "validation_completed",
  "run_id": "uuid-string",
  "layer": 1,
  "duration_ms": 500,
  "suggestion_count": 3,
  "timestamp": "2026-04-17T10:03:02Z"
}
```

> **注意**：spec 定义 `validation_completed` 是**单层校验完成**时发送（非全部完成），包含 `layer`、`duration_ms`、`suggestion_count` 字段。全部校验完成后由 `report_ready` 事件通知。

### 7. report_ready
```json
{
  "type": "report_ready",
  "run_id": "uuid-string",
  "report_id": "uuid-string",
  "overall_metrics": {
    "precision": 0.72,
    "recall": 0.86,
    "f1": 0.78,
    "mrr": 0.71,
    "ndcg": 0.79
  },
  "total_duration_seconds": 180,
  "validation_summary": {
    "layer1": {"status": "completed", "suggestion_count": 3},
    "layer2": {"status": "completed", "suggestion_count": 2},
    "layer3": {"status": "completed", "suggestion_count": 5},
    "layer4": {"status": "completed"},
    "layer5": {"status": "completed"},
    "layer6": {"status": "skipped"}
  },
  "timestamp": "2026-04-17T10:03:07Z"
}
```

> **注意**：严格按照 spec 定义，包含 `overall_metrics`、`total_duration_seconds`、`validation_summary` 字段。

### 8. run_failed
```json
{
  "type": "run_failed",
  "run_id": "uuid-string",
  "error_code": "LLM_TIMEOUT",
  "error_message": "LLM API 超时，重试 3 次后仍失败",
  "failed_at_case_id": "uuid-string",
  "timestamp": "2026-04-17T10:02:15Z"
}
```

> **注意**：严格按照 spec 定义，字段名为 `error_message`（非 `error`）、`failed_at_case_id`（UUID 类型，非数字 `failed_at_case`）。

### 9. heartbeat
```json
{
  "type": "heartbeat",
  "run_id": "uuid-string",
  "timestamp": "2026-04-17T10:01:45Z"
}
```

> **注意**：heartbeat 为系统级事件，不参与业务展示，仅用于前端断线检测。前端 **45 秒**未收到心跳判定断线（容忍 3 个心跳周期，防止网络抖动误判）。格式严格按照 spec 定义：`{run_id, timestamp}`，不包含 `channel` 字段（channel 由 SSE 连接路径本身区分）。

### 10. export_ready
```json
{
  "type": "export_ready",
  "task_id": "uuid-string",
  "report_id": "uuid-string",
  "download_url": "/api/exports/uuid-string/download",
  "file_size_bytes": 524288,
  "timestamp": "2026-04-17T10:05:00Z"
}
```

> **注意**：严格按照 spec 定义，字段名为 `task_id`（非 `export_id`），包含 `report_id` 和 `file_size_bytes`，不包含 `format` 和 `expires_at`。`export_ready` 通过**独立的 SSE 通道**推送：前端建立 `/api/sse/exports` 连接（按用户 ID 订阅），而非按 run_id 订阅。

### 导出失败处理

导出失败时，通过同一独立 SSE 通道 `/api/sse/exports` 推送错误通知，格式如下：

```json
{
  "type": "export_failed",
  "task_id": "uuid-string",
  "report_id": "uuid-string",
  "error": "PDF 生成失败：模板渲染异常",
  "timestamp": "2026-04-17T10:05:00Z"
}
```

> **注意**：`export_failed` 不是独立的事件类型定义，而是导出失败场景的推送格式，与 `export_ready` 共用同一通道。

## 实施要点

- 所有事件必须通过 `jsonable_encoder` 处理后再发布，防止 ORM/Pydantic 对象导致序列化崩溃
- `heartbeat` 间隔 15 秒，前端超时阈值 45 秒（容忍 3 个周期）
- `case_result` 推送单用例粒度结果，集合指标仅在 `test_completed` 中返回
- `export_ready` 使用独立 SSE 通道 `/api/sse/exports`（按用户 ID 订阅），不与测试运行频道混用
- `validation_started` 和 `validation_completed` 每层校验各发送一次（Layer 6 仅手动触发时发送）
- `run_failed` 的 `failed_at_case_id` 为 UUID 类型（非数字）
- 前端展示映射严格按 spec 定义：`run_started` 显示进度条并禁用运行按钮、`progress` 更新百分比和当前查询、`case_result` 更新用例列表状态等
