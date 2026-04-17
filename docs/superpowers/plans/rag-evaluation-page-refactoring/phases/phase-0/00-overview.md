# Phase 0: 核心工作流修复 — 总览

> **需求来源**: spec 文档 `01-phase-0-bug-fixes.md`
> **需求点数量**: 12 个
> **优先级**: P0（必须在 Phase 1 之前完成）

## 目标

修复书籍导入 5 个根因 + 批量测试 7 个根因，恢复核心工作流。

## 需求点清单

| # | 需求点 | 实施文件 | 根因 | 严重程度 |
|---|--------|---------|------|---------|
| 1 | EventSource 相对路径修复 | `01-eventsource-absolute-path.md` | 前端 dev server (5173) 和后端 (8000) 端口不同，SSE 请求 404 | CRITICAL |
| 2 | PDF/EPUB 二进制读取修复 | `02-pdf-epub-binary-parsing.md` | 用文本模式读取二进制文件，产生乱码 | CRITICAL |
| 3 | DASHSCOPE_API_KEY 环境变量校验 | `03-dashscope-api-key-validation.md` | 环境变量缺失，LLM 调用失败 | CRITICAL |
| 4 | Redis 降级到内存队列 | `04-redis-fallback-memory-queue.md` | SSE 依赖 Redis Pub/Sub，Redis 未启动时消息丢失 | HIGH |
| 5 | asyncio.create_task 强引用 | `05-asyncio-task-strong-reference.md` | Task 可能被 GC，导致任务静默终止 | HIGH |
| 6 | 前端 SSE 监听批量测试 | `06-frontend-sse-listening.md` | 前端发 POST 后等待 HTTP 响应，但批量测试远超 30 秒超时 | CRITICAL |
| 7 | runSingleTest 严格单用例 | `07-run-single-test-strict.md` | 代码 Bug：`_caseId` 参数被忽略，实际运行了所有测试 | CRITICAL |
| 8 | RetrievalService 复用实例 | `08-retrieval-service-reuse.md` | 每个用例创建新实例，并发时耗尽连接池 | HIGH |
| 9 | 本地并发控制替代分布式锁 | `09-local-concurrency-control.md` | 分布式锁对唯一 run_id 无意义，增加复杂度 | MEDIUM |
| 10 | 等待所有用例结果聚合 | `10-wait-all-results-aggregation.md` | 聚合指标可能不准确 | MEDIUM |
| 11 | SSE 心跳队列清理 | `11-sse-heartbeat-queue-cleanup.md` | 前端无消费，队列无限增长 | LOW |
| 12 | 前端 API 无超时 | `12-frontend-api-no-timeout.md` | 批量测试通常远超 30 秒 | HIGH |

## 验收标准

- [ ] 书籍导入：PDF/EPUB/TXT 三类文件均能正确提取文本内容
- [ ] SSE 连接：开发环境 (5173→8000) 和生产环境均成功
- [ ] 批量测试：前端实时显示进度百分比和当前处理用例
- [ ] 单个用例测试：传入 caseId 后仅执行对应用例
- [ ] 长时间任务 (10min+) 不会静默终止
- [ ] 128 用例测试不出现连接池耗尽
- [ ] Redis 不可用时批量测试仍能执行

## 实施顺序

1. **安装依赖**（最先执行）：
   ```bash
   cd backend && uv add json-repair
   # weasyprint 在 Phase 6 安装：uv add weasyprint
   ```
2. 修复书籍导入 5 个根因（1-5）
3. 修复批量测试 7 个根因（6-12）

---

**文档索引**: 
- 上一节: [00-overview.md](../../00-overview.md) — 项目概览
- 下一节: [01-eventsource-absolute-path.md](./01-eventsource-absolute-path.md) — 需求点 1
