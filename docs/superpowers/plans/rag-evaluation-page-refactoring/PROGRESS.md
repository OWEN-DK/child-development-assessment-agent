# 实施进度追踪

> **最后更新**: 2026-04-17
> **总体进度**: Phase 0-3 代码完成，Phase 5-8 方案已补全
> **总需求点数**: 108 个

---

## 总体状态

| Phase | 名称 | 需求点数 | 状态 | 完成度 |
|-------|------|---------|------|--------|
| Phase 0 | 核心工作流修复 | 12 | ✅ 代码完成 | 12/12 |
| Phase 1 | 数据模型创建 | 22 | ✅ 代码完成 | 22/22 |
| Phase 2 | SSE 工作流实现 | 10 | ✅ 代码完成 | 10/10 |
| Phase 3 | 前端页面实现 | 10 | ✅ 代码完成 | 10/10 |
| Phase 4 | 6 层校验引擎 | 17 | ✅ 代码完成 | 17/17 |
| Phase 5 | 推荐模式面板 + 配置/提示词编辑 | 11 | ✅ 方案完成 | 11/11 |
| Phase 6 | 趋势追踪 + 导出功能 | 8 | ✅ 方案完成 | 8/8 |
| Phase 7 | 提示词管理重构 | 10 | ✅ 方案完成 | 10/10 |
| Phase 8 | 配置管理优化 | 8 | ✅ 方案完成 | 8/8 |
| **合计** | | **108** | | **108/108** |

---

## Phase 0: 核心工作流修复 (12 个需求点)

| # | 需求点 | 实施文件 | 状态 | 备注 |
|---|--------|---------|------|------|
| 1 | EventSource 相对路径修复 | `01-eventsource-absolute-path.md` | ✅ | 前端 UploadDocumentModal + constants |
| 2 | PDF/EPUB 二进制读取修复 | `02-pdf-epub-binary-parsing.md` | ✅ | 新增 TXTParser，修复临时文件清理 |
| 3 | DASHSCOPE_API_KEY 环境变量校验 | `03-dashscope-api-key-validation.md` | ✅ | 新增 health_controller，启动时校验 |
| 4 | Redis 降级到内存队列 | `04-redis-fallback-memory-queue.md` | ✅ | SSEPublisher 增加 Redis 可用性检测 |
| 5 | asyncio.create_task 强引用 | `05-asyncio-task-strong-reference.md` | ✅ | AsyncTaskManager 增加 _active_tasks |
| 6 | 前端 SSE 监听批量测试 | `06-frontend-sse-listening.md` | ✅ | 新增 useSSE hook |
| 7 | runSingleTest 严格单用例 | `07-run-single-test-strict.md` | ✅ | run_test_case 已使用 rag_service |
| 8 | RetrievalService 复用实例 | `08-retrieval-service-reuse.md` | ✅ | execute_test_case 改用 rag_service |
| 9 | 本地并发控制替代分布式锁 | `09-local-concurrency-control.md` | ✅ | execute_batch 移除 DistributedLock |
| 10 | 等待所有用例结果聚合 | `10-wait-all-results-aggregation.md` | ✅ | execute_batch 等待所有结果后推送 |
| 11 | SSE 心跳队列清理 | `11-sse-heartbeat-queue-cleanup.md` | ✅ | subscribe 完善 finally 清理逻辑 |
| 12 | 前端 API 无超时 | `12-frontend-api-no-timeout.md` | ✅ | runAllTests 10s, runSingleTest 120s |

---

## Phase 1: 数据模型创建 (22 个需求点)

| # | 需求点 | 实施文件 | 状态 | 备注 |
|---|--------|---------|------|------|
| 1 | TestSet 模型定义 | `01-model-testset.md` | ✅ | RagEvalTestSet |
| 2 | TestSetCase 模型定义 | `02-model-testsetcase.md` | ✅ | 唯一约束 uk_rag_eval_test_set_case |
| 3 | TestCase 模型定义 | `03-model-testcase.md` | ✅ | 复用 TestDomain |
| 4 | TestRun 模型定义 | `04-model-testrun.md` | ✅ | A/B 测试字段 |
| 5 | TestRunResult 模型定义 | `05-model-testrunresult.md` | ✅ | hit_at_1/3/5 |
| 6 | TestCaseDraft 模型定义 | `06-model-testcasedraft.md` | ✅ | 状态机 |
| 7 | IntentAnnotation 模型定义 | `07-model-intentannotation.md` | ✅ | 唯一约束 |
| 8 | ConfigVersion 模型定义 | `08-model-configversion.md` | ✅ | JSON 快照 |
| 9 | PromptVersion 模型定义 | `09-model-promptversion.md` | ✅ | 多 FK |
| 10 | ConfigChangeSet 模型定义 | `10-model-configchangeset.md` | ✅ | |
| 11 | ConfigChangeSetPrompt 模型定义 | `11-model-configchangesetprompt.md` | ✅ | 唯一约束 |
| 12 | TestReport 模型定义 | `12-model-testreport.md` | ✅ | 6 层校验 JSON |
| 13 | TuningSuggestionRecord 模型定义 | `13-model-tuningsuggestionrecord.md` | ✅ | |
| 14 | PromptSuggestionRecord 模型定义 | `14-model-promptsuggestionrecord.md` | ✅ | |
| 15 | IgnoredSuggestion 模型定义 | `15-model-ignoredsuggestion.md` | ✅ | 双 FK |
| 16 | QueryIntentLog 模型定义 | `16-model-queryintentlog.md` | ✅ | |
| 17 | SynonymQueryPair 模型定义 | `17-model-synonymquerypair.md` | ✅ | |
| 18 | 22 个索引定义 | `18-indexes-definition.md` | ✅ | 22 命名 + FK 自动 = 35 |
| 19 | Enum 映射验证 | `19-enum-mapping-validation.md` | ✅ | values_callable 全部显式 |
| 20 | RagEval Enums 定义 | `20-enums-definition.md` | ✅ | 16 个 Enum |
| 21 | __init__.py 导出模块 | `21-init-module.md` | ✅ | 17 模型 + 16 Enum |

---

## Phase 2: SSE 工作流实现 (10 个需求点)

| # | 需求点 | 实施文件 | 状态 | 备注 |
|---|--------|---------|------|------|
| 1 | 10 种 SSE 事件定义 | `01-sse-event-definitions.md` | ✅ | Pydantic模型 + TypeScript类型，字段与spec严格一致 |
| 2 | RagEvalTaskManager 实现 | `02-async-task-manager.md` | ✅ | 组合SSEPublisher，不管理心跳（由subscribe负责），不硬编码校验事件 |
| 3 | SSEPublisher 增强 | `03-sse-publisher.md` | ✅ | publish_event、心跳15秒、心跳格式对齐spec(ISO 8601) |
| 4 | SSE 控制器路由 | `04-sse-controller-routes.md` | ✅ | /api/runs/{run_id}/sse, /api/sse/exports |
| 5 | 前端 SSE 客户端 | `05-frontend-sse-client.md` | ✅ | SseClient类 + useTestRunSse/useExportSse hooks |
| 6 | 断线重连机制 | `06-disconnect-reconnect-mechanism.md` | ✅ | 指数退避(1s→30s) + 5步恢复流程 |
| 7 | 进度恢复 API | `07-progress-recovery-api.md` | ✅ | GET /api/runs/{run_id}/progress + /status + /results |
| 8 | 心跳队列清理 | `08-heartbeat-queue-cleanup.md` | ✅ | put_nowait + MAX_QUEUE_SIZE=100 + finally完善 |
| 9 | jsonable_encoder 处理 | `09-jsonable-encoder-handling.md` | ✅ | SSEPublisher.publish + RagEvalTaskManager._publish 双重保护 |
| 10 | 导出 SSE 通道 | `10-export-sse-channel.md` | ✅ | export_ready/export_failed + run_export_task包装器 |

> **审核修复记录**：
> - P0: 删除 RagEvalTaskManager 中的 start_heartbeat/stop_heartbeat，心跳完全由 SSEPublisher.subscribe() 负责
> - P1: 心跳格式从 `{channel, timestamp(monotonic)}` 改为 `{run_id, timestamp(ISO 8601)}`
> - P1: 从 RagEvalTaskManager 中移除校验事件硬编码（Phase 4 由校验引擎自行发布）
> - P2: report_ready 补充 report_url 字段
> - P2: 进度 API datetime 序列化 + total_cases=0 除零保护

---

## Phase 3: 前端页面实现 (10 个需求点)

| # | 需求点 | 实施文件 | 状态 | 备注 |
|---|--------|---------|------|------|
| 1 | `/rag-eval/*` 路由配置 | `01-routes-rag-eval.md` | ✅ | React Router 7 路由配置，懒加载，RagEvalLayout |
| 2 | 测试集列表页 | `02-page-testset-list.md` | ✅ | TestSetListPage + Zustand store，搜索/筛选/CRUD |
| 3 | 测试集详情页 | `03-page-testset-detail.md` | ✅ | TestSetDetailPage，用例列表/运行测试/添加移除 |
| 4 | 草稿审核页 | `04-page-draft-review.md` | ✅ | DraftReviewPage，状态筛选/批量归入/批量拒绝 |
| 5 | 运行历史列表页 | `05-page-run-list.md` | ✅ | RunListPage，状态/测试集/时间范围筛选 |
| 6 | 运行详情页 | `06-page-run-detail.md` | ✅ | RunDetailPage，SSE 实时进度/指标卡片/结果过滤 |
| 7 | 评估报告页 | `07-page-report.md` | ✅ | ReportPage，5 Tab 布局/6层校验占位/导出功能 |
| 8 | 删除旧路由 `/rag-evaluation` | `08-delete-old-routes.md` | ✅ | 删除 rag-evaluation 目录，更新 router + menu |
| 9 | 删除 OneClickOptimize 组件 | `09-delete-oneclickoptimize.md` | ✅ | 随旧目录一起删除 |
| 10 | SPA 回退路由 | `10-spa-fallback-route.md` | ✅ | server.py 添加 `/{full_path:path}` 回退 |

---

## Phase 4: 6 层校验引擎 (17 个需求点)

| # | 需求点 | 实施文件 | 状态 | 备注 |
|---|--------|---------|------|------|
| 1 | ValidationOrchestrator 编排器 | `01-validation-orchestrator.md` | ✅ | 10 测试通过 |
| 2 | Layer 1: 规则引擎 | `02-layer1-rule-engine.md` | ✅ | 11 测试通过 |
| 3 | Layer 2: 历史对比 | `03-layer2-history-comparison.md` | ✅ | 9 测试通过 |
| 4 | Layer 3: LLM 诊断 | `04-layer3-llm-diagnosis.md` | ✅ | 12 测试通过 |
| 5 | Layer 4a: Golden 覆盖度 | `05-layer4a-golden-coverage.md` | ✅ | 4 测试通过 |
| 6 | Layer 4b: 分块质量评分 | `06-layer4b-chunk-quality.md` | ✅ | 5 测试通过 |
| 7 | Layer 4c: 文档时效性 | `07-layer4c-document-staleness.md` | ✅ | 5 测试通过 |
| 8 | Layer 5a: Embedding 质量 | `08-layer5a-embedding-quality.md` | ✅ | 7 测试通过 |
| 9 | Layer 5b: 意图识别准确率 | `09-layer5b-intent-accuracy.md` | ✅ | 5 测试通过 |
| 10 | Layer 5c: 错误模式分组 | `10-layer5c-error-patterns.md` | ✅ | 6 测试通过 |
| 11 | Layer 6a: 回归检测 | `11-layer6a-regression-detection.md` | ✅ | 5 测试通过 |
| 12 | Layer 6b: 交叉验证 | `12-layer6b-cross-validation.md` | ✅ | 6 测试通过 |
| 13 | Layer 6c: 成本效果分析 | `13-layer6c-cost-effectiveness.md` | ✅ | 6 测试通过 |
| 14 | Layer 6d: A/B 影子测试 | `14-layer6d-ab-shadow-test.md` | ✅ | 6 测试通过 |
| 15 | 超时与降级策略 | `15-timeout-degradation-strategy.md` | ✅ | 4 测试通过 |
| 16 | 并发限制（最多 3 个） | `16-concurrency-limit.md` | ✅ | 2 测试通过 |
| 17 | Layer 6 手动触发 API | `17-layer6-manual-trigger-api.md` | ✅ | 2 测试通过 |

---

## Phase 5: 推荐模式面板 + 配置/提示词编辑 (11 个需求点)

| # | 需求点 | 实施文件 | 状态 | 备注 |
|---|--------|---------|------|------|
| 1 | 推荐模式面板（三种模式） | `01-recommendation-panel-three-modes.md` | ✅ | 方案已补全 |
| 2 | 审查面板（抽屉式） | `02-review-panel-drawer.md` | ✅ | 方案已补全 |
| 3 | 配置对比视图 | `03-comparison-view-config.md` | ✅ | 方案已补全 |
| 4 | 提示词对比视图 | `04-comparison-view-prompt.md` | ✅ | 方案已补全 |
| 5 | 采纳→审查→保存三步流程 | `05-adopt-review-save-flow.md` | ✅ | 方案已补全 |
| 6 | 原子保存事务 | `06-atomic-save-transaction.md` | ✅ | 方案已补全 |
| 7 | 配置热重载 | `07-config-hot-reload.md` | ✅ | 方案已补全 |
| 8 | ConfigCache 单例 | `08-config-cache-singleton.md` | ✅ | 方案已补全 |
| 9 | 已忽略建议列表 | `09-ignored-suggestions-list.md` | ✅ | 方案已补全 |
| 10 | 恢复忽略建议 | `10-restore-ignored-suggestion.md` | ✅ | 方案已补全 |
| 11 | 面板布局适配 | `11-panel-layout-adaptation.md` | ✅ | 方案已补全 |

---

## Phase 6: 趋势追踪 + 导出功能 (8 个需求点)

| # | 需求点 | 实施文件 | 状态 | 备注 |
|---|--------|---------|------|------|
| 1 | 趋势图组件（均值 + 误差线） | `01-trend-chart-component.md` | ✅ | 方案已补全 |
| 2 | 多指标叠加展示 | `02-multi-metric-overlay.md` | ✅ | 方案已补全 |
| 3 | 配置版本对比 | `03-config-version-comparison.md` | ✅ | 方案已补全 |
| 4 | 配置版本回滚 | `04-config-version-rollback.md` | ✅ | 方案已补全 |
| 5 | PDF 导出（后端异步） | `05-pdf-export-async.md` | ✅ | 方案已补全 |
| 6 | CSV 导出（前端） | `06-csv-export-frontend.md` | ✅ | 方案已补全 |
| 7 | JSON 导出（前端） | `07-json-export-frontend.md` | ✅ | 方案已补全 |
| 8 | 导出任务并发限制 | `08-export-task-concurrency-limit.md` | ✅ | 方案已补全 |

---

## Phase 7: 提示词管理重构 (10 个需求点)

| # | 需求点 | 实施文件 | 状态 | 备注 |
|---|--------|---------|------|------|
| 1 | PromptMetadata 模型 | `01-promptmetadata-model.md` | ✅ | 方案已补全 |
| 2 | PromptVersion 调整 | `02-promptversion-adjustment.md` | ✅ | 方案已补全 |
| 3 | 提示词列表页 | `03-prompt-list-page.md` | ✅ | 方案已补全 |
| 4 | 提示词编辑页 | `04-prompt-edit-page.md` | ✅ | 方案已补全 |
| 5 | 提示词版本对比页 | `05-prompt-version-comparison.md` | ✅ | 方案已补全 |
| 6 | 提示词测试沙箱页 | `06-prompt-test-sandbox.md` | ✅ | 方案已补全 |
| 7 | 影响分析引擎 | `07-impact-analysis-engine.md` | ✅ | 方案已补全 |
| 8 | 代码引用扫描器 | `08-code-reference-scanner.md` | ✅ | 方案已补全 |
| 9 | 变量校验器 | `09-variable-validator.md` | ✅ | 方案已补全 |
| 10 | 配置参数依赖检测器 | `10-config-dependency-detector.md` | ✅ | 方案已补全 |

---

## Phase 8: 配置管理优化 (8 个需求点)

| # | 需求点 | 实施文件 | 状态 | 备注 |
|---|--------|---------|------|------|
| 1 | 配置元数据中文补充 | `01-config-metadata-chinese.md` | ✅ | 方案已补全 |
| 2 | 配置主页（分组卡片） | `02-config-home-grouped-cards.md` | ✅ | 方案已补全 |
| 3 | 分类配置页 | `03-config-category-page.md` | ✅ | 方案已补全 |
| 4 | 实时校验 | `04-realtime-validation.md` | ✅ | 方案已补全 |
| 5 | 影响范围展示 | `05-impact-range-display.md` | ✅ | 方案已补全 |
| 6 | 配置版本管理 | `06-config-version-management.md` | ✅ | 方案已补全 |
| 7 | 配置校验引擎 | `07-config-validation-engine.md` | ✅ | 方案已补全 |
| 8 | 配置冲突检测 | `08-config-conflict-detection.md` | ✅ | 方案已补全 |

---

**图例**: ⬜ 未开始 | 🔄 进行中 | ✅ 完成 | ❌ 阻塞
