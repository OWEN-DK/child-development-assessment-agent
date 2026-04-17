# Phase 2: SSE 工作流实现 — 总览

> **需求来源**: spec 文档 `03-sse-workflow.md`
> **需求点数量**: 10 个
> **优先级**: P1

## 目标

实现 SSE 实时推送工作流，支持断线重连，心跳队列无内存泄漏。

## 需求点清单

> **注意**: spec 定义 10 种 SSE 事件。`export_failed` 不是 spec 定义的独立事件类型，而是导出失败时的错误处理场景，在独立导出 SSE 通道中推送（与 `export_ready` 共用 `/api/sse/exports` 端点），因此合并到需求点 10 中。前端通过 `type` 字段区分 `export_ready` 和 `export_failed`。

| # | 需求点 | 实施文件 | 说明 |
|---|--------|---------|------|
| 1 | 10 种 SSE 事件定义 | `01-sse-event-definitions.md` | run_started, progress, case_result, test_completed, validation_started, validation_completed, report_ready, run_failed, heartbeat, export_ready |
| 2 | AsyncTaskManager 实现 | `02-async-task-manager.md` | 异步任务管理（start_task, 强引用） |
| 3 | SSEPublisher 实现 | `03-sse-publisher.md` | SSE 事件发布（jsonable_encoder, 队列清理） |
| 4 | SSE 控制器路由 | `04-sse-controller-routes.md` | `/api/runs/{run_id}/sse`, `/api/sse/exports` |
| 5 | 前端 SSE 客户端 | `05-frontend-sse-client.md` | EventSource, 断线重连, 45 秒心跳检测 |
| 6 | 断线重连机制 | `06-disconnect-reconnect-mechanism.md` | 5 步恢复流程 + Redis 进度缓存 |
| 7 | 进度恢复 API | `07-progress-recovery-api.md` | `GET /api/runs/{run_id}/progress` |
| 8 | 心跳队列清理 | `08-heartbeat-queue-cleanup.md` | 前端断开时清理队列 |
| 9 | jsonable_encoder 处理 | `09-jsonable-encoder-handling.md` | SSE 结果必须 JSON 序列化 |
| 10 | 导出 SSE 通道 | `10-export-sse-channel.md` | 独立 SSE 通道 `/api/sse/exports`，含 export_ready 和 export_failed 推送 |

## 验收标准

- [ ] 10 种 SSE 事件定义完整（严格按 spec 字段格式）
- [ ] 前端能接收并展示实时进度
- [ ] 断线重连机制工作正常（5 步恢复 + Redis 进度缓存）
- [ ] 心跳队列无内存泄漏（前端断开时清理）
- [ ] SSE 推送结果经 jsonable_encoder 处理
- [ ] 后台任务不抛出未捕获异常

## 关键规则

- `heartbeat` 每 15 秒发送，格式 `{run_id, timestamp}`，前端 45 秒未收到判定断线（容忍 3 个周期）
- `case_result` 中单个用例展示 hit@k，集合指标在 `test_completed` 中返回
- `export_ready` 通过独立 SSE 通道 `/api/sse/exports` 推送（按用户 ID 订阅）
- `validation_started` 和 `validation_completed` 每层校验各发送一次（Layer 6 仅手动触发时发送）
- 断线重连：Redis 优先读取进度，降级到数据库查询 TestRunResult 聚合
- 所有事件字段名和类型严格按 spec 定义，不得自行增减字段

---

**文档索引**: 
- 上一节: [Phase 1 总览](../phase-1/00-overview.md)
- 下一节: [01-sse-event-definitions.md](./01-sse-event-definitions.md) — 需求点 1
