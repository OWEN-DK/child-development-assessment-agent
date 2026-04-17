# Phase 3: LLM 调用追踪 - Overview

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.
> **状态:** 📋 方案构建完成，待实施
> **优先级:** 中
> **预计工期:** 5 人天
> **依赖前置:** Phase 1 (LLM 多提供商 + 热配置)、Phase 2A (RAG 评估工作流重塑，TestRun 数据在 MySQL 中可用)

**Goal:** 引入类似 Langfuse 的简化版 LLM 调用追踪系统，全量记录模型的输入、输出及实时调用参数，支持故障排查 (Debug)、效果分析和成本监控。

**Architecture:** 采用 `contextvars` 实现 task-local 的 Trace/Span 上下文传递，LangGraph 节点自动埋点创建 Span，异步队列写入 MySQL 存储，前端提供 Trace Viewer 可视化界面。

**Tech Stack:** Python 3.13, FastAPI 0.135, SQLAlchemy 2.0, Pydantic v2, contextvars, asyncio, React 19, TypeScript

---

## 实施顺序

> **分阶段实施策略**: 为降低风险，分三阶段落地：Phase 3.1 完成数据模型与存储设计（核心路径）；Phase 3.2 实现调用链路集成与异步处理；Phase 3.3 完成 API、前端视图与全链路验证。

| 步骤 | 内容 | 状态 | 阶段 | 详细文档 |
|------|------|------|------|----------|
| 1 | Trace/Span 数据模型 | ⏳ 待实现 | Phase 3.1 | [01-trace-model.md](./05-phase-3-01-trace-model.md) |
| 2 | 存储设计与优化 | ⏳ 待实现 | Phase 3.1 | [02-storage-design.md](./05-phase-3-02-storage-design.md) |
| 3 | 调用链路集成与埋点 | ⏳ 待实现 | Phase 3.2 | [03-instrumentation.md](./05-phase-3-03-instrumentation.md) |
| 4 | 数据上报与异步处理 | ⏳ 待实现 | Phase 3.2 | [04-data-processing.md](./05-phase-3-04-data-processing.md) |
| 5 | 前端追踪视图 | ⏳ 待实现 | Phase 3.3 | [05-dashboard.md](./05-phase-3-05-dashboard.md) |
| 6 | 链路详情与分析 | ⏳ 待实现 | Phase 3.3 | [06-trace-details.md](./05-phase-3-06-trace-details.md) |
| 7 | API 扩展 | ⏳ 待实现 | Phase 3.3 | [07-api-extension.md](./05-phase-3-07-api-extension.md) |

---

## 前置准备

- [x] Phase 1 LLM 供应商重构完成并上线
- [x] Phase 2A RAG 评估工作流重塑完成，TestRun/TestRunResult 数据在 MySQL 中可用
- [x] `LLMCallLog` 模型已存在（需扩展字段）
- [x] LangGraph 工作流稳定运行（NodePre → ValidationNode → AssessmentNode → RetrievalNode → ScoringNode → ReportingNode）

---

## 核心架构

```
┌─────────────────────────────────────────────────────────┐
│                    业务层调用                              │
│  LangGraph Nodes / RagTestManager / LLMServiceFactory    │
└──────────────────────┬──────────────────────────────────┘
                       ▼
┌─────────────────────────────────────────────────────────┐
│              TraceContext (contextvars)                   │
│  trace_context() 创建 Trace                              │
│  create_span() 维护父子关系栈                              │
└──────────────────────┬──────────────────────────────────┘
                       ▼
┌─────────────────────────────────────────────────────────┐
│              TraceWriter (异步队列)                        │
│  采样策略 → 截断处理 → 批量写入                            │
└──────────────────────┬──────────────────────────────────┘
                       ▼
┌─────────────────────────────────────────────────────────┐
│              存储层                                        │
│  traces 表 (Trace) + llm_call_logs 表 (Span)              │
│  可选：完整内容本地文件存储                                 │
└─────────────────────────────────────────────────────────┘
```

### 关键设计决策

| 决策点 | 选择 | 理由 |
|--------|------|------|
| 上下文传递 | `contextvars` (task-local) | 原生支持 asyncio，每个任务独立上下文，并发安全 |
| 写入方式 | 异步队列 + 批量写入 | 不阻塞主流程，降低数据库写入压力 |
| 采样策略 | 随机采样 + 错误全量保留 | 平衡存储成本与问题排查能力 |
| 内容截断 | 默认 8000 字符，完整内容可选存文件 | 避免单条记录过大影响查询性能 |
| Span 层级 | Trace → Node Span → LLM Call Span | 与 LangGraph 节点结构对齐，便于追踪 |
| 成本计算 | 模型定价表 + Token 计数 | 自动估算，未配置模型显示 "未配置" |

---

## 🎯 验收标准

### 核心功能验收

> **⚠️ 测试路径说明**: 以下测试路径假设项目测试目录结构为 `tests/unit/` 和 `tests/integration/`。实施前请确认实际测试目录结构，若不同则相应调整路径。

| 检查项 | 测试命令 | 预期结果 |
|--------|----------|----------|
| Trace/Span 创建 | `pytest tests/unit/tracing/test_trace_context.py -v` | contextvars 正确传递，父子关系正确 |
| LangGraph 自动埋点 | `pytest tests/integration/tracing/test_langgraph_integration.py -v` | 每个节点执行前后自动创建 Span |
| 异步写入队列 | `pytest tests/unit/tracing/test_trace_writer.py -v` | 数据正确入队，不阻塞主流程 |
| 采样策略生效 | `pytest tests/unit/tracing/test_sampling.py -v` | 采样率配置正确，错误全量保留 |
| 截断存储 | `pytest tests/unit/tracing/test_truncation.py -v` | 超长内容正确截断，完整内容可选存文件 |
| API 接口 | `pytest tests/integration/tracing/test_tracing_api.py -v` | 8 个 API 接口功能正常 |
| 成本计算 | `pytest tests/unit/tracing/test_cost_calculation.py -v` | 成本计算准确，未配置模型处理正确 |
| 前端 Trace Viewer | `cd frontend && npm run test -- tracing --watchAll=false` | 列表、详情、筛选功能正常 |

### 性能基线验收

| 检查项 | 基准环境 | 测量方法 | 预期结果 |
|--------|----------|----------|----------|
| Trace 创建开销 | 4C8G, 本地 MySQL | 对比开启/关闭追踪的端到端耗时 | 开销 <5% |
| 异步队列延迟 | 100 条/秒写入 | 记录入队到入库的时间差 | P99 <500ms |
| 截断处理耗时 | 100KB 输入内容 | 单条截断操作耗时 | <1ms |
| 采样率准确性 | 采样率 0.1，1000 次调用 | 实际写入记录数 | 90-110 条 (±10%) |

---

## 🔙 回滚计划

| 风险场景 | 回滚操作 | 回滚耗时 | 影响范围 |
|---------|---------|---------|---------|
| TraceContext 上下文污染 | 关闭追踪功能开关，清空 contextvars | 自动降级 | 仅追踪功能不可用，业务无影响 |
| 异步队列积压导致 OOM | 清空队列，降低采样率至 0 | <1 分钟 | 追踪数据丢失，业务无影响 |
| 数据库写入性能下降 | 降低采样率，增加批量写入间隔 | <5 分钟 | 追踪数据延迟入库 |
| 前端 Trace Viewer 报错 | 隐藏 Traces 标签页，不影响其他监控功能 | 前端条件渲染 | 仅追踪视图不可用 |

---

## ⚠️ 风险登记册

| 风险项 | 发生概率 | 影响程度 | 缓解措施 |
|-------|----------|----------|----------|
| contextvars 在并发场景上下文丢失 | 低 | 高 | 编写并发测试验证，使用 `asyncio.create_task()` 时显式传递 trace_id |
| 异步队列写入失败导致数据丢失 | 中 | 中 | 队列满时降级为同步写入 + 告警；支持重试机制 |
| 截断存储导致调试信息不完整 | 低 | 中 | 完整内容可选存本地文件，Trace 详情提供文件路径链接 |
| 采样率配置不当导致存储爆炸 | 中 | 高 | 默认采样率 1.0，提供 TTL 自动清理（默认 30 天）；监控存储增长趋势 |
| LangGraph 节点埋点影响工作流性能 | 低 | 中 | 埋点逻辑异步化，仅记录必要信息；支持功能开关 |

---

**上一阶段:** [Phase 2C](./04-phase-2c-tuning-engine.md)  
**下一阶段:** [附录 A: 数据库迁移](./appendix-a-database-migration.md)

**子文档索引:**

| 步骤 | 内容 | 状态 | 阶段 | 详细文档 |
|------|------|------|------|----------|
| 1 | Trace/Span 数据模型 | ⏳ 待实现 | Phase 3.1 | [01-trace-model.md](./05-phase-3-01-trace-model.md) - traces 表 + LLMCallLog 扩展 + 索引设计 |
| 2 | 存储设计与优化 | ⏳ 待实现 | Phase 3.1 | [02-storage-design.md](./05-phase-3-02-storage-design.md) - 截断策略 + TTL 清理 + 冷热分层 |
| 3 | 调用链路集成 | ⏳ 待实现 | Phase 3.2 | [03-instrumentation.md](./05-phase-3-03-instrumentation.md) - TraceContext + LangGraph 埋点 + 测试执行集成 |
| 4 | 数据上报与处理 | ⏳ 待实现 | Phase 3.2 | [04-data-processing.md](./05-phase-3-04-data-processing.md) - 异步队列 + 采样策略 + 批量写入 |
| 5 | 前端追踪视图 | ⏳ 待实现 | Phase 3.3 | [05-dashboard.md](./05-phase-3-05-dashboard.md) - TraceListView + FilterBar + 标签页集成 |
| 6 | 链路详情与分析 | ⏳ 待实现 | Phase 3.3 | [06-trace-details.md](./05-phase-3-06-trace-details.md) - SpanTreeView + SpanDetailPanel + 成本分析 |
| 7 | API 扩展 | ⏳ 待实现 | Phase 3.3 | [07-api-extension.md](./05-phase-3-07-api-extension.md) - 8 个新接口 + 请求/响应格式 |

> **分阶段实施策略**: 为降低风险，分三阶段落地：Phase 3.1 完成数据模型与存储设计（核心路径）；Phase 3.2 实现调用链路集成与异步处理；Phase 3.3 完成 API、前端视图与全链路验证。
> **任务依赖关系**: 存储设计依赖数据模型完成，调用链路集成依赖 TraceContext 完成，数据上报依赖异步队列完成，前端视图依赖 API 完成。

---

## 📌 全局说明

1. **测试目录适配**: 所有测试用例路径默认适配 `tests/` 根目录，可根据项目实际测试目录结构调整
2. **导入路径适配**: 代码示例中的导入路径基于项目现有目录结构，如需调整可根据实际模块位置修改
3. **全链路集成测试流程**: 完成所有开发后执行：
   1. 开启追踪功能（采样率 1.0）
   2. 执行一次完整 RAG 测试集运行
   3. 验证 traces 表和 llm_call_logs 表数据完整
   4. 通过 API 查询 Trace 详情，验证 Span 层级树正确
   5. 前端 Trace Viewer 查看追踪记录，验证展示正常
   6. 运行所有单元测试
4. **部署注意事项**: 异步队列使用 Redis 作为缓冲（若可用），否则使用内存队列；TTL 清理任务通过 APScheduler 定时执行
