# 03 - SSE 事件与工作流

> **本文档包含**: 测试集运行工作流、SSE 事件定义、前端展示映射、断线重连机制

---

## 3.5 测试集运行工作流

```
用户操作                          后端处理
─────────                        ─────────
1. 选择测试集
   ↓
2. 点击"运行测试"              →  创建 TestRun (status=pending) → 执行每个用例 → 收集结果
3. 等待完成 (SSE 进度推送)      ←  SSE: progress/case_result/test_completed
   ↓
4. 查看报告                    →  触发 6 层校验 → 生成 TestReport → SSE: report_ready
5. 查看调优建议                →  报告内嵌
   ↓
6. 应用建议 (可选)             →  创建 ConfigChangeSet (原子事务) → 热更新
   ↓
7. 复测验证                    →  回到步骤 1，用新配置重新运行
```

**运行中取消**: 用户可在运行详情页点击 `[取消运行]`，后端设置 TestRun.status = `cancelled`，停止后续用例执行，已完成的用例结果保留。

### 3.5.1 SSE 事件定义

> **需求**: 前端依赖 SSE 事件实现进度条、实时状态和错误提示，必须定义完整的事件契约。

**事件类型**:

| 事件 | 类型 | 触发时机 | 数据字段 |
|------|------|---------|---------|
| `run_started` | 业务 | 测试开始 | `run_id`, `test_set_id`, `total_cases`, `config_version` |
| `progress` | 业务 | 每完成一个用例 | `run_id`, `current_case`, `total_cases`, `current_query`, `elapsed_seconds` |
| `case_result` | 业务 | 单个用例完成 | `run_id`, `case_id`, `query`, `hit_at_1`, `hit_at_3`, `hit_at_5`, `matched_doc_ids`, `matched_doc_scores`, `status` (passed/failed) |
| `test_completed` | 业务 | 所有用例执行完毕 | `run_id`, `total_cases`, `passed_cases`, `overall_metrics` (precision/recall/f1/mrr/ndcg) |
| `validation_started` | 业务 | 校验开始 | `run_id`, `layer` (1-6，Layer 6 仅手动触发时发送) |
| `validation_completed` | 业务 | 单层校验完成 | `run_id`, `layer`, `duration_ms`, `suggestion_count` |
| `report_ready` | 业务 | 校验全部完成且报告已生成 | `run_id`, `report_id`, `overall_metrics`, `total_duration_seconds`, `validation_summary` |
| `run_failed` | 业务 | 测试异常中断 | `run_id`, `error_code`, `error_message`, `failed_at_case_id` |
| `heartbeat` | 系统 | 每 15 秒定时发送 | `run_id`, `timestamp` (ISO 8601) |
| `export_ready` | 业务 | PDF 导出任务完成 | `task_id`, `report_id`, `download_url`, `file_size_bytes` |

**QueryIntentLog 写入时机**:
- 在 **每个用例执行时** 自动写入：当 TestRun 执行单个用例时，系统对查询进行意图自动分类（使用 LLM），分类结果写入 `QueryIntentLog` 表
- 写入时机在 `case_result` 事件触发 **之前**，确保 Layer 5b 校验时数据已就绪
- LLM 调用成本计入该用例的执行成本，不额外收费
- 若意图分类 LLM 调用失败（超时/异常），该用例的 `QueryIntentLog` 记录不写入，Layer 5b 校验时跳过该用例的意图准确率计算

**注意**:
- `case_result` 中单个用例无法计算 Precision/Recall/F1（集合指标），改为 `hit_at_k`（命中检测）。集合指标在 `test_completed` 事件中返回。
- `heartbeat` 为系统级事件，不参与业务展示，仅用于前端断线检测。前端 **45 秒**未收到心跳判定断线（容忍 3 个心跳周期，防止网络抖动误判）。
- `export_ready` 事件通过**独立的 SSE 通道**推送：前端建立 `/api/sse/exports` 连接（按用户 ID 订阅），而非按 run_id 订阅。导出任务完成后通过此通道推送给用户。

**前端展示映射**:

| SSE 事件 | 前端行为 |
|---------|---------|
| `run_started` | 显示进度条 (0%)，禁用"运行"按钮，显示 `[取消运行]` |
| `progress` | 更新进度条百分比，显示当前查询文本 |
| `case_result` | 更新用例列表状态 (✅/❌)，显示 hit@k |
| `test_completed` | 显示"用例执行完成，正在生成诊断报告..." |
| `validation_started` | 显示对应校验层状态为"处理中..." |
| `validation_completed` | 显示校验层状态为"完成"，展示建议数量 |
| `report_ready` | 跳转到报告页 `/rag-eval/reports/{report_id}`，启用"运行"按钮 |
| `run_failed` | 弹出错误提示，显示失败用例位置，启用"运行"按钮 |
| `heartbeat` | 不展示，仅重置 45 秒断线计时器 |
| `export_ready` | 自动触发 PDF 下载，显示"导出完成"提示 |

**断线重连机制**:

| 场景 | 处理策略 |
|------|---------|
| SSE 连接端点 | `GET /api/runs/{run_id}/sse` — 前端通过此端点建立 SSE 连接，订阅指定 run_id 的事件 |
| 导出 SSE 端点 | `GET /api/sse/exports` — 前端通过此端点建立 SSE 连接，按用户 ID 订阅导出任务事件 |
| 网络断开/页面刷新 | 前端重连后调用 `GET /api/runs/{run_id}/status` 查询当前运行状态 |
| 重连后状态恢复 | 根据 `status` 字段决定：`running` → 重新订阅 SSE 并请求最近进度；`completed` → 直接跳转报告页；`failed` → 显示错误 |
| 心跳机制 | 后端每 15 秒发送 `heartbeat` 事件 `{run_id, timestamp}`，前端 **45 秒**未收到心跳判定断线（容忍 3 个周期） |
| 后端清理 | 前端断开连接时，后端从 SSE 订阅者列表中移除对应 clientId，防止内存泄漏 |
| 进度恢复 API | `GET /api/runs/{run_id}/progress` 返回 `{current_case, total_cases, last_case_result, elapsed_seconds}`，用于断线后恢复进度条显示 |

**断线重连完整数据恢复流程**:
1. **前端检测断线**: 45 秒未收到 heartbeat → 判定断线 → 显示"连接中断，正在重连..."
2. **查询运行状态**: 调用 `GET /api/runs/{run_id}/status` → 返回 `{status, completed_cases, total_cases, last_event_type}`
3. **根据状态恢复**:
   - **status = running**:
     a. 重新建立 SSE 连接 `GET /api/runs/{run_id}/sse`
     b. 调用 `GET /api/runs/{run_id}/progress` 获取最近进度 → 恢复进度条百分比和已完成的用例列表
     c. 从 `last_case_result` 恢复最近一个用例的 hit@k 展示
     d. 后续通过 SSE 接收新的事件继续更新
   - **status = completed**:
     a. 若 TestReport.status = completed → 直接跳转到报告页 `/rag-eval/reports/{report_id}`
     b. 若 TestReport.status = processing → 跳转到报告页，展示"校验进行中..."，通过 SSE 监听 `validation_completed` 和 `report_ready` 事件
   - **status = failed**:
     a. 调用 `GET /api/runs/{run_id}` 获取完整运行详情（包含已完成的用例结果）
     b. 展示失败页面，显示已完成的用例数和失败原因
   - **status = cancelled**: 展示取消页面，显示已完成的用例数
4. **进度数据持久化**: TestRun 执行过程中，每完成一个用例，后端将进度写入 Redis（key: `run_progress:{run_id}`，TTL: 24 小时，结构: `{current_case, total_cases, last_case_result, elapsed_seconds}`）。`GET /api/runs/{run_id}/progress` 优先从 Redis 读取，若 Redis 无数据则从数据库查询 TestRunResult 表聚合计算（性能较差，仅作为降级方案）
5. **断线期间的事件丢失**: 若断线期间 TestRun 已完成，前端重连后无法通过 SSE 接收历史事件。此时前端通过 `GET /api/runs/{run_id}/results` 获取完整的用例结果列表（分页），一次性渲染到页面

---

**文档索引**: 
- 上一节: [02-data-model.md](./02-data-model.md) — 核心数据模型
- 下一节: [04-frontend-pages.md](./04-frontend-pages.md) — 前端页面设计
