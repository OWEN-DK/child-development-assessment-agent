# 文档结构说明

## 📁 文件组织

本文档将 RAG 评估平台重构实施计划拆分为多个独立模块，**一个文件只对应一个需求点**，不得合并。

### 核心文档结构

```
rag-evaluation-page-refactoring/
├── README.md                              # 主索引文件（入口）+ 核心实施规则
├── PROGRESS.md                            # 进度追踪（按需求点 checkbox）
├── DOCUMENT_STRUCTURE.md                  # 本文档：需求点与实施文件映射表
├── 00-overview.md                         # 项目概览：背景目标、验收标准、架构
│
├── phases/
│   ├── phase-0/                           # Phase 0: 核心工作流修复 (12 个需求点)
│   │   ├── 00-overview.md                 # Phase 0 总览
│   │   ├── 01-eventsource-absolute-path.md
│   │   ├── 02-pdf-epub-binary-parsing.md
│   │   ├── 03-dashscope-api-key-validation.md
│   │   ├── 04-redis-fallback-memory-queue.md
│   │   ├── 05-asyncio-task-strong-reference.md
│   │   ├── 06-frontend-sse-listening.md
│   │   ├── 07-run-single-test-strict.md
│   │   ├── 08-retrieval-service-reuse.md
│   │   ├── 09-local-concurrency-control.md
│   │   ├── 10-wait-all-results-aggregation.md
│   │   ├── 11-sse-heartbeat-queue-cleanup.md
│   │   └── 12-frontend-api-no-timeout.md
│   │
│   ├── phase-1/                           # Phase 1: 数据模型创建 (22 个需求点)
│   │   ├── 00-overview.md                 # Phase 1 总览
│   │   ├── 01-model-testset.md
│   │   ├── 02-model-testsetcase.md
│   │   ├── 03-model-testcase.md
│   │   ├── 04-model-testrun.md
│   │   ├── 05-model-testrunresult.md
│   │   ├── 06-model-testcasedraft.md
│   │   ├── 07-model-intentannotation.md
│   │   ├── 08-model-promptmetadata.md
│   │   ├── 09-model-configversion.md
│   │   ├── 10-model-promptversion.md
│   │   ├── 11-model-configchangeset.md
│   │   ├── 12-model-configchangesetprompt.md
│   │   ├── 13-model-testreport.md
│   │   ├── 14-model-tuningsuggestionrecord.md
│   │   ├── 15-model-promptsuggestionrecord.md
│   │   ├── 16-model-ignoredsuggestion.md
│   │   ├── 17-model-queryintentlog.md
│   │   ├── 18-model-synonymquerypair.md
│   │   ├── 19-indexes-definition.md
│   │   ├── 20-enum-mapping-validation.md
│   │   ├── 21-enums-definition.md
│   │   └── 22-init-module.md
│   │
│   ├── phase-2/                           # Phase 2: SSE 工作流实现 (10 个需求点)
│   │   ├── 00-overview.md                 # Phase 2 总览
│   │   ├── 01-sse-event-definitions.md
│   │   ├── 02-async-task-manager.md
│   │   ├── 03-sse-publisher.md
│   │   ├── 04-sse-controller-routes.md
│   │   ├── 05-frontend-sse-client.md
│   │   ├── 06-disconnect-reconnect-mechanism.md
│   │   ├── 07-progress-recovery-api.md
│   │   ├── 08-heartbeat-queue-cleanup.md
│   │   ├── 09-jsonable-encoder-handling.md
│   │   └── 10-export-sse-channel.md
│   │
│   ├── phase-3/                           # Phase 3: 前端页面实现 (10 个需求点)
│   │   ├── 00-overview.md                 # Phase 3 总览
│   │   ├── 01-routes-rag-eval.md
│   │   ├── 02-page-testset-list.md
│   │   ├── 03-page-testset-detail.md
│   │   ├── 04-page-draft-review.md
│   │   ├── 05-page-run-list.md
│   │   ├── 06-page-run-detail.md
│   │   ├── 07-page-report.md
│   │   ├── 08-delete-old-routes.md
│   │   ├── 09-delete-oneclickoptimize.md
│   │   └── 10-spa-fallback-route.md
│   │
│   ├── phase-4/                           # Phase 4: 6 层校验引擎 (17 个需求点)
│   │   ├── 00-overview.md                 # Phase 4 总览
│   │   ├── 01-validation-orchestrator.md
│   │   ├── 02-layer1-rule-engine.md
│   │   ├── 03-layer2-history-comparison.md
│   │   ├── 04-layer3-llm-diagnosis.md
│   │   ├── 05-layer4a-golden-coverage.md
│   │   ├── 06-layer4b-chunk-quality.md
│   │   ├── 07-layer4c-document-staleness.md
│   │   ├── 08-layer5a-embedding-quality.md
│   │   ├── 09-layer5b-intent-accuracy.md
│   │   ├── 10-layer5c-error-patterns.md
│   │   ├── 11-layer6a-regression-detection.md
│   │   ├── 12-layer6b-cross-validation.md
│   │   ├── 13-layer6c-cost-effectiveness.md
│   │   ├── 14-layer6d-ab-shadow-test.md
│   │   ├── 15-timeout-degradation-strategy.md
│   │   └── 16-concurrency-limit.md
│   │
│   ├── phase-5/                           # Phase 5: 推荐模式面板 + 配置/提示词编辑 (11 个需求点)
│   │   ├── 00-overview.md                 # Phase 5 总览
│   │   ├── 01-recommendation-panel-three-modes.md
│   │   ├── 02-review-panel-drawer.md
│   │   ├── 03-comparison-view-config.md
│   │   ├── 04-comparison-view-prompt.md
│   │   ├── 05-adopt-review-save-flow.md
│   │   ├── 06-atomic-save-transaction.md
│   │   ├── 07-config-hot-reload.md
│   │   ├── 08-config-cache-singleton.md
│   │   ├── 09-ignored-suggestions-list.md
│   │   ├── 10-restore-ignored-suggestion.md
│   │   └── 11-panel-layout-adaptation.md
│   │
│   ├── phase-6/                           # Phase 6: 趋势追踪 + 导出功能 (8 个需求点)
│   │   ├── 00-overview.md                 # Phase 6 总览
│   │   ├── 01-trend-chart-component.md
│   │   ├── 02-multi-metric-overlay.md
│   │   ├── 03-config-version-comparison.md
│   │   ├── 04-config-version-rollback.md
│   │   ├── 05-pdf-export-async.md
│   │   ├── 06-csv-export-frontend.md
│   │   ├── 07-json-export-frontend.md
│   │   └── 08-export-task-concurrency-limit.md
│   │
│   ├── phase-7/                           # Phase 7: 提示词管理重构 (10 个需求点)
│   │   ├── 00-overview.md                 # Phase 7 总览
│   │   ├── 01-promptmetadata-model.md
│   │   ├── 02-promptversion-adjustment.md
│   │   ├── 03-prompt-list-page.md
│   │   ├── 04-prompt-edit-page.md
│   │   ├── 05-prompt-version-comparison.md
│   │   ├── 06-prompt-test-sandbox.md
│   │   ├── 07-impact-analysis-engine.md
│   │   ├── 08-code-reference-scanner.md
│   │   ├── 09-variable-validator.md
│   │   └── 10-config-dependency-detector.md
│   │
│   └── phase-8/                           # Phase 8: 配置管理优化 (8 个需求点)
│       ├── 00-overview.md                 # Phase 8 总览
│       ├── 01-config-metadata-chinese.md
│       ├── 02-config-home-grouped-cards.md
│       ├── 03-config-category-page.md
│       ├── 04-realtime-validation.md
│       ├── 05-impact-range-display.md
│       ├── 06-config-version-management.md
│       ├── 07-config-validation-engine.md
│       └── 08-config-conflict-detection.md
```

---

## 📋 需求点与实施文件映射表

> **每个需求点对应一个实施文件，不得遗漏和跳过。**

### Phase 0: 核心工作流修复 (12 个需求点)

| 需求点序号 | 需求点名称 | 实施文件 | spec 来源 |
|-----------|-----------|---------|----------|
| 1 | EventSource 相对路径修复 | `01-eventsource-absolute-path.md` | 01-phase-0-bug-fixes.md 2.0.1 |
| 2 | PDF/EPUB 二进制读取修复 | `02-pdf-epub-binary-parsing.md` | 01-phase-0-bug-fixes.md 2.0.1 |
| 3 | DASHSCOPE_API_KEY 环境变量校验 | `03-dashscope-api-key-validation.md` | 01-phase-0-bug-fixes.md 2.0.1 |
| 4 | Redis 降级到内存队列 | `04-redis-fallback-memory-queue.md` | 01-phase-0-bug-fixes.md 2.0.1 |
| 5 | asyncio.create_task 强引用 | `05-asyncio-task-strong-reference.md` | 01-phase-0-bug-fixes.md 2.0.1 |
| 6 | 前端 SSE 监听批量测试 | `06-frontend-sse-listening.md` | 01-phase-0-bug-fixes.md 2.0.2 |
| 7 | runSingleTest 严格单用例 | `07-run-single-test-strict.md` | 01-phase-0-bug-fixes.md 2.0.2 |
| 8 | RetrievalService 复用实例 | `08-retrieval-service-reuse.md` | 01-phase-0-bug-fixes.md 2.0.2 |
| 9 | 本地并发控制替代分布式锁 | `09-local-concurrency-control.md` | 01-phase-0-bug-fixes.md 2.0.2 |
| 10 | 等待所有用例结果聚合 | `10-wait-all-results-aggregation.md` | 01-phase-0-bug-fixes.md 2.0.2 |
| 11 | SSE 心跳队列清理 | `11-sse-heartbeat-queue-cleanup.md` | 01-phase-0-bug-fixes.md 2.0.2 |
| 12 | 前端 API 无超时 | `12-frontend-api-no-timeout.md` | 01-phase-0-bug-fixes.md 2.0.2 |

### Phase 1: 数据模型创建 (22 个需求点)

| 需求点序号 | 需求点名称 | 实施文件 | spec 来源 |
|-----------|-----------|---------|----------|
| 1 | TestSet 模型定义 | `01-model-testset.md` | 02-data-model.md |
| 2 | TestSetCase 模型定义 | `02-model-testsetcase.md` | 02-data-model.md |
| 3 | TestCase 模型定义 | `03-model-testcase.md` | 02-data-model.md |
| 4 | TestRun 模型定义 | `04-model-testrun.md` | 02-data-model.md |
| 5 | TestRunResult 模型定义 | `05-model-testrunresult.md` | 02-data-model.md |
| 6 | TestCaseDraft 模型定义 | `06-model-testcasedraft.md` | 02-data-model.md |
| 7 | IntentAnnotation 模型定义 | `07-model-intentannotation.md` | 02-data-model.md |
| 8 | PromptMetadata 模型定义 | `08-model-promptmetadata.md` | 02-data-model.md + 07a-prompt-data-model.md |
| 9 | ConfigVersion 模型定义 | `09-model-configversion.md` | 02-data-model.md |
| 10 | PromptVersion 模型定义 | `10-model-promptversion.md` | 02-data-model.md |
| 11 | ConfigChangeSet 模型定义 | `11-model-configchangeset.md` | 02-data-model.md |
| 12 | ConfigChangeSetPrompt 模型定义 | `12-model-configchangesetprompt.md` | 02-data-model.md |
| 13 | TestReport 模型定义 | `13-model-testreport.md` | 02-data-model.md |
| 14 | TuningSuggestionRecord 模型定义 | `14-model-tuningsuggestionrecord.md` | 02-data-model.md |
| 15 | PromptSuggestionRecord 模型定义 | `15-model-promptsuggestionrecord.md` | 02-data-model.md |
| 16 | IgnoredSuggestion 模型定义 | `16-model-ignoredsuggestion.md` | 02-data-model.md |
| 17 | QueryIntentLog 模型定义 | `17-model-queryintentlog.md` | 02-data-model.md |
| 18 | SynonymQueryPair 模型定义 | `18-model-synonymquerypair.md` | 02-data-model.md |
| 19 | 22 个索引定义 | `18-indexes-definition.md` | 02-data-model.md 3.5 |
| 20 | Enum 映射验证 | `19-enum-mapping-validation.md` | CLAUDE.md + 02-data-model.md |
| 21 | RagEval Enums 定义 | `20-enums-definition.md` | 02-data-model.md |
| 22 | __init__.py 导出模块 | `21-init-module.md` | 02-data-model.md |

### Phase 2: SSE 工作流实现 (10 个需求点)

| 需求点序号 | 需求点名称 | 实施文件 | spec 来源 |
|-----------|-----------|---------|----------|
| 1 | 10 种 SSE 事件定义（严格按 spec 字段） | `01-sse-event-definitions.md` | 03-sse-workflow.md 3.5.1 |
| 2 | AsyncTaskManager 实现 | `02-async-task-manager.md` | 03-sse-workflow.md |
| 3 | SSEPublisher 实现 | `03-sse-publisher.md` | 03-sse-workflow.md |
| 4 | SSE 控制器路由 | `04-sse-controller-routes.md` | 03-sse-workflow.md |
| 5 | 前端 SSE 客户端 | `05-frontend-sse-client.md` | 03-sse-workflow.md |
| 6 | 断线重连机制 | `06-disconnect-reconnect-mechanism.md` | 03-sse-workflow.md |
| 7 | 进度恢复 API | `07-progress-recovery-api.md` | 03-sse-workflow.md |
| 8 | 心跳队列清理 | `08-heartbeat-queue-cleanup.md` | 03-sse-workflow.md |
| 9 | jsonable_encoder 处理 | `09-jsonable-encoder-handling.md` | CLAUDE.md + 03-sse-workflow.md |
| 10 | 导出 SSE 通道（含 export_failed） | `10-export-sse-channel.md` | 03-sse-workflow.md |

### Phase 3: 前端页面实现 (10 个需求点)

| 需求点序号 | 需求点名称 | 实施文件 | spec 来源 |
|-----------|-----------|---------|----------|
| 1 | `/rag-eval/*` 路由配置 | `01-routes-rag-eval.md` | 04-frontend-pages.md 3.6 |
| 2 | 测试集列表页 | `02-page-testset-list.md` | 04-frontend-pages.md 4.4 |
| 3 | 测试集详情页 | `03-page-testset-detail.md` | 04-frontend-pages.md 4.5 |
| 4 | 草稿审核页 | `04-page-draft-review.md` | 04-frontend-pages.md 4.6 |
| 5 | 运行历史列表页 | `05-page-run-list.md` | 04-frontend-pages.md 4.7 |
| 6 | 运行详情页 | `06-page-run-detail.md` | 04-frontend-pages.md 4.8 |
| 7 | 评估报告页 | `07-page-report.md` | 04-frontend-pages.md 4.1 |
| 8 | 删除旧路由 `/rag-evaluation` | `08-delete-old-routes.md` | 04-frontend-pages.md 3.6 |
| 9 | 删除 OneClickOptimize 组件 | `09-delete-oneclickoptimize.md` | 04-frontend-pages.md 3.6 |
| 10 | SPA 回退路由 | `10-spa-fallback-route.md` | CLAUDE.md |

### Phase 4: 6 层校验引擎 (17 个需求点)

| 需求点序号 | 需求点名称 | 实施文件 | spec 来源 |
|-----------|-----------|---------|----------|
| 1 | ValidationOrchestrator 编排器 | `01-validation-orchestrator.md` | 05-validation-layers.md 3.2 |
| 2 | Layer 1: 规则引擎 | `02-layer1-rule-engine.md` | 05-validation-layers.md 5.1 |
| 3 | Layer 2: 历史对比 | `03-layer2-history-comparison.md` | 05-validation-layers.md 5.2 |
| 4 | Layer 3: LLM 诊断 | `04-layer3-llm-diagnosis.md` | 05-validation-layers.md 5.3 |
| 5 | Layer 4a: Golden 覆盖度 | `05-layer4a-golden-coverage.md` | 05-validation-layers.md 5.4.1 |
| 6 | Layer 4b: 分块质量评分 | `06-layer4b-chunk-quality.md` | 05-validation-layers.md 5.4.2 |
| 7 | Layer 4c: 文档时效性 | `07-layer4c-document-staleness.md` | 05-validation-layers.md 5.4.3 |
| 8 | Layer 5a: Embedding 质量 | `08-layer5a-embedding-quality.md` | 05-validation-layers.md 5.5.1 |
| 9 | Layer 5b: 意图识别准确率 | `09-layer5b-intent-accuracy.md` | 05-validation-layers.md 5.5.2 |
| 10 | Layer 5c: 错误模式分组 | `10-layer5c-error-patterns.md` | 05-validation-layers.md 5.5.3 |
| 11 | Layer 6a: 回归检测 | `11-layer6a-regression-detection.md` | 05-validation-layers.md 5.6.1 |
| 12 | Layer 6b: 交叉验证 | `12-layer6b-cross-validation.md` | 05-validation-layers.md 5.6.2 |
| 13 | Layer 6c: 成本效果分析 | `13-layer6c-cost-effectiveness.md` | 05-validation-layers.md 5.6.3 |
| 14 | Layer 6d: A/B 影子测试 | `14-layer6d-ab-shadow-test.md` | 05-validation-layers.md 5.6.4 |
| 15 | 超时与降级策略 | `15-timeout-degradation-strategy.md` | 05-validation-layers.md 3.3 |
| 16 | 并发限制（最多 3 个） | `16-concurrency-limit.md` | 05-validation-layers.md 3.3 |
| 17 | Layer 6 手动触发 API | `17-layer6-manual-trigger-api.md` | 05-validation-layers.md 5.6 |

### Phase 5: 推荐模式面板 + 配置/提示词编辑 (11 个需求点)

| 需求点序号 | 需求点名称 | 实施文件 | spec 来源 |
|-----------|-----------|---------|----------|
| 1 | 推荐模式面板（三种模式） | `01-recommendation-panel-three-modes.md` | 04-frontend-pages.md 4.2 |
| 2 | 审查面板（抽屉式） | `02-review-panel-drawer.md` | 04-frontend-pages.md 4.2 |
| 3 | 配置对比视图 | `03-comparison-view-config.md` | 04-frontend-pages.md 4.2 |
| 4 | 提示词对比视图 | `04-comparison-view-prompt.md` | 04-frontend-pages.md 4.2 |
| 5 | 采纳→审查→保存三步流程 | `05-adopt-review-save-flow.md` | 04-frontend-pages.md 4.2 |
| 6 | 原子保存事务 | `06-atomic-save-transaction.md` | 04-frontend-pages.md 4.2 |
| 7 | 配置热重载 | `07-config-hot-reload.md` | 04-frontend-pages.md 4.2 |
| 8 | ConfigCache 单例 | `08-config-cache-singleton.md` | 04-frontend-pages.md 4.2 |
| 9 | 已忽略建议列表 | `09-ignored-suggestions-list.md` | 04-frontend-pages.md 4.2 |
| 10 | 恢复忽略建议 | `10-restore-ignored-suggestion.md` | 04-frontend-pages.md 4.2 |
| 11 | 面板布局适配 | `11-panel-layout-adaptation.md` | 04-frontend-pages.md 4.2 |

### Phase 6: 趋势追踪 + 导出功能 (8 个需求点)

| 需求点序号 | 需求点名称 | 实施文件 | spec 来源 |
|-----------|-----------|---------|----------|
| 1 | 趋势图组件（均值 + 误差线） | `01-trend-chart-component.md` | 04-frontend-pages.md 4.9 |
| 2 | 多指标叠加展示 | `02-multi-metric-overlay.md` | 04-frontend-pages.md 4.9 |
| 3 | 配置版本对比 | `03-config-version-comparison.md` | 04-frontend-pages.md 4.9 |
| 4 | 配置版本回滚 | `04-config-version-rollback.md` | 04-frontend-pages.md 4.9 |
| 5 | PDF 导出（后端异步） | `05-pdf-export-async.md` | 04-frontend-pages.md 4.10 |
| 6 | CSV 导出（前端） | `06-csv-export-frontend.md` | 04-frontend-pages.md 4.10 |
| 7 | JSON 导出（前端） | `07-json-export-frontend.md` | 04-frontend-pages.md 4.10 |
| 8 | 导出任务并发限制 | `08-export-task-concurrency-limit.md` | 04-frontend-pages.md 4.10 |

### Phase 7: 提示词管理重构 (10 个需求点)

| 需求点序号 | 需求点名称 | 实施文件 | spec 来源 |
|-----------|-----------|---------|----------|
| 1 | PromptMetadata 模型 | `01-promptmetadata-model.md` | 07a-prompt-data-model.md |
| 2 | PromptVersion 调整 | `02-promptversion-adjustment.md` | 07a-prompt-data-model.md |
| 3 | 提示词列表页 | `03-prompt-list-page.md` | 07b-prompt-frontend-pages.md |
| 4 | 提示词编辑页 | `04-prompt-edit-page.md` | 07b-prompt-frontend-pages.md |
| 5 | 提示词版本对比页 | `05-prompt-version-comparison.md` | 07b-prompt-frontend-pages.md |
| 6 | 提示词测试沙箱页 | `06-prompt-test-sandbox.md` | 07b-prompt-frontend-pages.md |
| 7 | 影响分析引擎 | `07-impact-analysis-engine.md` | 07c-prompt-impact-analysis.md |
| 8 | 代码引用扫描器 | `08-code-reference-scanner.md` | 07c-prompt-impact-analysis.md |
| 9 | 变量校验器 | `09-variable-validator.md` | 07c-prompt-impact-analysis.md |
| 10 | 配置参数依赖检测器 | `10-config-dependency-detector.md` | 07c-prompt-impact-analysis.md |

### Phase 8: 配置管理优化 (8 个需求点)

| 需求点序号 | 需求点名称 | 实施文件 | spec 来源 |
|-----------|-----------|---------|----------|
| 1 | 配置元数据中文补充 | `01-config-metadata-chinese.md` | 08a-config-metadata.md |
| 2 | 配置主页（分组卡片） | `02-config-home-grouped-cards.md` | 08b-config-frontend-pages.md |
| 3 | 分类配置页 | `03-config-category-page.md` | 08b-config-frontend-pages.md |
| 4 | 实时校验 | `04-realtime-validation.md` | 08b-config-frontend-pages.md |
| 5 | 影响范围展示 | `05-impact-range-display.md` | 08b-config-frontend-pages.md |
| 6 | 配置版本管理 | `06-config-version-management.md` | 08b-config-frontend-pages.md |
| 7 | 配置校验引擎 | `07-config-validation-engine.md` | 08c-config-validation.md |
| 8 | 配置冲突检测 | `08-config-conflict-detection.md` | 08c-config-validation.md |

---

## 📖 使用指南

### 阅读顺序

1. **入口**：从 [`README.md`](./README.md) 开始，了解项目整体与核心规则
2. **概览**：阅读 [`00-overview.md`](./00-overview.md)，了解背景目标、验收标准、架构
3. **映射表**：阅读本文档，了解需求点与实施文件的对应关系
4. **按 Phase 执行**：按 Phase 0→8 顺序，每个 Phase 先读 `00-overview.md`，再按序号逐个实施

### 实施文件模板

每个实施文件必须包含以下结构：

```markdown
# {需求点名称}

> **需求来源**: spec 文档 `{spec_file}` 中 `{section}` 节
> **所属 Phase**: Phase {N}

## 需求定义

{来自 spec 文档的完整需求描述}

## 验收标准

- [ ] {验收标准 1}
- [ ] {验收标准 2}

## 涉及文件

| 文件路径 | 操作 | 说明 |
|---------|------|------|
| `backend/src/...` | 新增/修改/删除 | {说明} |

## 实现方案

### 后端实现

{完整的 Python 代码实现}

### 前端实现（如适用）

{完整的 TypeScript/React 代码实现}

### 数据库变更（如适用）

{完整的 DDL 语句或 SQLAlchemy 模型定义}

## 测试方案

{测试用例定义，TDD-Red 阶段必须先写测试}

## 注意事项

{CLAUDE.md 相关规则、踩坑提醒}
```

---

## 🔧 文档维护

### 添加新内容

如需补充某个需求点的详细实施，直接编辑对应的实施文件即可。

### 更新现有内容

直接编辑对应的实施文件。所有修改应：
- 保持代码示例的完整性
- 包含必要的导入语句
- 提供测试步骤和预期结果
- 遵守"一个文件只对应一个需求点"的原则

---

## 🔗 相关文档

- [需求文档](../../specs/2026-04-16-rag-evaluation-page-refactoring/) - RAG 评估平台重构需求 (v15.0)
- [RAG 系统完整文档](../../../RAG_SYSTEM_COMPLETE_DOCUMENTATION.md) - RAG 系统技术细节
- [RAG 流水线架构](../../../../.ai/rag_pipeline.md) - 核心模块与 API 端点
- [搜索优化计划](../rag-search-optimization/) - 参考文档结构

---

**最后更新：** 2026-04-16
**文档版本：** 0.1 (初始框架)
**维护者：** AI Assistant
