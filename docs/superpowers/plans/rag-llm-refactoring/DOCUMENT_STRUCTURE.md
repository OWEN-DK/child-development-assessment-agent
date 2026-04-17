# 文档结构说明

## 📁 文件组织

本文档将 RAG 评估与 LLM 多模型提供商重构方案拆分为多个独立模块，便于管理和维护。

### 核心文档结构

```
rag-llm-refactoring/
├── README.md                              # 主索引文件（入口）
├── PROGRESS.md                            # 进度追踪
├── 00-overview.md                         # 项目概览与文件结构变更
│
├── # Phase 1: LLM 多提供商 + 热配置
├── 01-phase-1-00-overview.md              # Phase 1 总览与目标
├── 01-phase-1-01-config-layer.md          # 配置层设计与参数模型
├── 01-phase-1-02-factory-refactor.md      # 工厂重构与多提供商适配
├── 01-phase-1-03-hot-reload.md            # 热更新机制与事件总线集成
├── 01-phase-1-04-call-sites.md            # 调用点改造与向后兼容
├── 01-phase-1-05-dependencies.md          # 依赖升级与兼容性处理
├── 01-phase-1-llm-providers.md            # Phase 1 汇总文档
│
├── # Phase 2A: RAG 评估工作流重塑
├── 02-phase-2a-00-overview.md             # Phase 2A 总览与目标
├── 02-phase-2a-01-data-model.md           # 数据模型设计与数据库迁移
├── 02-phase-2a-02-execution-path.md       # 执行路径与核心逻辑实现
├── 02-phase-2a-03-report-lifecycle.md     # 报告生命周期管理
├── 02-phase-2a-04-test-case-generation.md # 测试用例自动生成与审核
├── 02-phase-2a-05-frontend-ui.md          # 前端界面与交互设计
├── 02-phase-2a-rag-workflow.md            # Phase 2A 汇总文档
│
├── # Phase 2B: 提示词/配置收拢
├── 03-phase-2b-00-overview.md             # Phase 2B 总览与目标
├── 03-phase-2b-01-prompt-migration.md     # 提示词迁移与PromptManager接入
├── 03-phase-2b-02-config-migration.md     # 配置迁移与ConfigManager接入
├── 03-phase-2b-03-magic-value-cleanup.md  # 魔法值清理与常量定义
├── 03-phase-2b-prompt-config-cleanup.md   # Phase 2B 汇总文档
│
├── # Phase 2C: 智能调参建议引擎
├── 04-phase-2c-00-overview.md             # Phase 2C 总览与目标
├── 04-phase-2c-01-rule-engine.md          # 规则引擎层实现
├── 04-phase-2c-02-historical-comparison.md# 历史对比层实现
├── 04-phase-2c-03-llm-diagnosis.md        # LLM诊断层实现
├── 04-phase-2c-tuning-engine.md           # Phase 2C 汇总文档
│
├── # Phase 3: LLM 调用追踪
├── 05-phase-3-00-overview.md              # Phase 3 总览与目标
├── 05-phase-3-01-trace-model.md           # Trace/Span数据模型
├── 05-phase-3-02-integration.md           # 调用链路集成与埋点
├── 05-phase-3-03-frontend-views.md        # 前端追踪视图实现
├── 05-phase-3-llm-tracing.md              # Phase 3 汇总文档
│
├── appendix-a-database-migration.md       # 数据库迁移清单
├── appendix-b-api-reference.md            # API 接口变更参考
├── appendix-c-risk-control.md             # 风险控制与回滚策略
├── appendix-d-verification-report.md      # 验证与调整报告
│
└── DOCUMENT_STRUCTURE.md                  # 本文档
```

### 文档拆分策略

所有Phase均采用"总览+细分模块"的分层结构，每个模块独立成文件：

#### Phase 1: LLM 多提供商 + 热配置
| 模块 | 拆分后文件 | 说明 |
|------|-----------|------|
| 总览与目标 | `01-phase-1-00-overview.md` | Phase 1 整体目标、范围、进度安排 |
| 配置层设计 | `01-phase-1-01-config-layer.md` | 配置层设计、参数模型、全局凭证分离 |
| 工厂重构 | `01-phase-1-02-factory-refactor.md` | Provider 抽象、多提供商适配、工厂重构 |
| 热更新机制 | `01-phase-1-03-hot-reload.md` | 零停机热更新、事件总线集成、配置校验层 |
| 调用点改造 | `01-phase-1-04-call-sites.md` | 现有调用点改造、向后兼容处理 |
| 依赖处理 | `01-phase-1-05-dependencies.md` | 依赖升级、兼容性处理、测试验证 |
| 汇总文档 | `01-phase-1-llm-providers.md` | Phase 1 完整方案汇总、验收标准 |

#### Phase 2A: RAG 评估工作流重塑
| 模块 | 拆分后文件 | 说明 |
|------|-----------|------|
| 总览与目标 | `02-phase-2a-00-overview.md` | Phase 2A 整体目标、范围、进度安排 |
| 数据模型 | `02-phase-2a-01-data-model.md` | 数据模型设计、数据库迁移清单 |
| 执行路径 | `02-phase-2a-02-execution-path.md` | 核心逻辑实现、执行路径设计 |
| 报告生命周期 | `02-phase-2a-03-report-lifecycle.md` | 报告生成、管理、导出、删除流程 |
| 测试用例生成 | `02-phase-2a-04-test-case-generation.md` | 测试用例自动生成、草稿审核流程 |
| 前端UI | `02-phase-2a-05-frontend-ui.md` | 前端界面设计、交互流程、状态管理 |
| 汇总文档 | `02-phase-2a-rag-workflow.md` | Phase 2A 完整方案汇总、验收标准 |

#### Phase 2B: 提示词/配置收拢
| 模块 | 拆分后文件 | 说明 |
|------|-----------|------|
| 总览与目标 | `03-phase-2b-00-overview.md` | Phase 2B 整体目标、范围、进度安排 |
| 提示词扫描与盘点 | `03-phase-2b-01-prompt-scan.md` | 全代码库硬编码提示词扫描、清单梳理、分类 |
| 提示词迁移与接入 | `03-phase-2b-02-prompt-migration.md` | 提示词入库、PromptManager接入、fallback配置 |
| 提示词校验与测试 | `03-phase-2b-03-prompt-validation.md` | 提示词一致性校验、功能回归测试、灰度验证 |
| 配置扫描与盘点 | `03-phase-2b-04-config-scan.md` | 全代码库硬编码配置扫描、清单梳理、分类 |
| 配置迁移与接入 | `03-phase-2b-05-config-migration.md` | 配置入库、ConfigManager接入、热重载验证 |
| 魔法值清理与重构 | `03-phase-2b-06-magic-value-cleanup.md` | 魔法值清理、常量定义、代码规范落地 |
| 兼容性与降级处理 | `03-phase-2b-07-compatibility.md` | 降级策略、回滚方案、历史版本兼容 |
| 汇总文档 | `03-phase-2b-prompt-config-cleanup.md` | Phase 2B 完整方案汇总、验收标准 |

#### Phase 2C: 智能调参建议引擎
| 模块 | 拆分后文件 | 说明 |
|------|-----------|------|
| 总览与目标 | `04-phase-2c-00-overview.md` | Phase 2C 整体目标、架构、验收标准、回滚计划 |
| 规则引擎 | `04-phase-2c-01-rule-engine.md` | 规则配置化 (MySQL) + 核心实现 + 冲突检测 |
| 历史对比分析 | `04-phase-2c-02-history-analyzer.md` | 数据关联链路 + 相似匹配 + 效果追踪 |
| LLM 诊断 | `04-phase-2c-03-llm-diagnoser.md` | Prompt 设计 + Bad Case 聚合 + json-repair 输出解析 |
| 统一引擎 + API | `04-phase-2c-04-engine-api.md` | 引擎入口 + 3 个 API 接口 + DI 注册 |
| 前端集成 (MVP) | `04-phase-2c-05-frontend-mvp.md` | 建议面板 + 一键优化组件 + API 客户端 |
| TDD 测试策略 | `04-phase-2c-06-testing.md` | 测试文件清单 + 红绿重构步骤 + Fixture 定义 |
| 汇总文档 | `04-phase-2c-tuning-engine.md` | Phase 2C 完整方案汇总、文档索引 |

#### Phase 3: LLM 调用追踪
| 模块 | 拆分后文件 | 说明 |
|------|-----------|------|
| 总览与目标 | `05-phase-3-00-overview.md` | Phase 3 整体目标、架构、验收标准、回滚计划 |
| Trace/Span数据模型 | `05-phase-3-01-trace-model.md` | traces 表 + LLMCallLog 扩展 + 索引设计 + 成本计算 |
| 存储设计与优化 | `05-phase-3-02-storage-design.md` | 截断策略 + TTL 清理 + 配置集中化 |
| 调用链路集成与埋点 | `05-phase-3-03-instrumentation.md` | TraceContext + LangGraph 埋点 + 测试执行集成 + LLM 调用集成 |
| 数据上报与异步处理 | `05-phase-3-04-data-processing.md` | TraceWriter 异步队列 + 采样策略 + 队列满降级 |
| 前端追踪视图 | `05-phase-3-05-dashboard.md` | TraceListView + TraceFilterBar + 标签页集成 |
| 链路详情与分析 | `05-phase-3-06-trace-details.md` | TraceDetailDrawer + SpanTreeView + SpanDetailPanel + 成本分析 |
| API 扩展 | `05-phase-3-07-api-extension.md` | 8 个新接口 + TraceService + 成本/延迟/错误分析 |
| 汇总文档 | `05-phase-3-llm-tracing.md` | Phase 3 完整方案汇总、文档索引 |

#### Phase 4: 系统配置页面重构
| 模块 | 拆分后文件 | 说明 |
|------|-----------|------|
| 总览与目标 | `06-phase-4-00-overview.md` | Phase 4 整体目标、文件结构变更、架构说明、验收标准 |
| P0 Bug 修复 | `06-phase-4-01-bug-fixes.md` | 3 个阻塞性 Bug 修复（reset 端点、保存字段、分类过滤）+ 技术债务清理 |
| 专家模式实施 | `06-phase-4-02-expert-mode.md` | 侧边栏 + 手风琴 + 搜索 + 修改标记 + 撤销 + 响应式布局 |
| ConfigStore 扩展 | `06-phase-4-03-store-extension.md` | 新增状态/Actions、originalValues 追踪、localStorage 持久化、降级策略 |
| 后端 API 扩展 | `06-phase-4-04-backend-api.md` | reset/validate/export/import/health 5 个 API 端点 + 健康诊断服务 |
| 向导模式实施 | `06-phase-4-05-wizard-mode.md` | 3 步流程 + 跳过 + 推荐提示 + 模式切换 + 数据共享 |

#### 通用文档
| Spec 章节 | 拆分后文件 | 说明 |
|-----------|-----------|------|
| 概述与目标 | `00-overview.md` | 包含文件结构变更、架构图、依赖管理 |
| 数据库迁移清单 | `appendix-a-database-migration.md` | Alembic 迁移脚本清单 |
| API 接口变更参考 | `appendix-b-api-reference.md` | API 接口变更说明、兼容处理 |
| 风险控制与迁移策略 | `appendix-c-risk-control.md` | 回滚策略、灰度发布、安全审计 |
| 验证与调整报告 | `appendix-d-verification-report.md` | 测试验证报告、问题调整记录 |

---

## 📖 使用指南

### 阅读顺序

1. **入口**：从 [`README.md`](./README.md) 开始，了解项目整体
2. **概览**：阅读 [`00-overview.md`](./00-overview.md)，了解文件结构和架构
3. **实施**：按顺序执行各个 Phase：
   - [`Phase 1`](./01-phase-1-llm-providers.md) - LLM 多提供商 + 热配置
   - [`Phase 2A`](./02-phase-2a-rag-workflow.md) - RAG 评估工作流重塑
   - [`Phase 2B`](./03-phase-2b-prompt-config-cleanup.md) - 提示词/配置收拢
   - [`Phase 2C`](./04-phase-2c-tuning-engine.md) - 智能调参建议引擎
   - [`Phase 3`](./05-phase-3-llm-tracing.md) - LLM 调用追踪
   - [`Phase 4`](./06-phase-4-00-overview.md) - 系统配置页面重构
4. **参考**：查阅附录文档获取迁移清单和风险控制指南

### 任务追踪

每个 Phase 文档都使用 checkbox (`- [ ]`) 语法，方便追踪进度：

```markdown
- [ ] **Step 1: 任务描述**
```

实施时，将已完成的步骤标记为：

```markdown
- [x] **Step 1: 任务描述**
```

---

## 🔧 文档维护

### 添加新内容

如需补充某个 Phase 的详细任务，可以：

1. 创建新的文件，如 `01-phase-1-llm-providers.md`
2. 在 `README.md` 中更新链接
3. 在 `PROGRESS.md` 中标记进度

### 更新现有内容

直接编辑对应的 Phase 文件即可。所有修改应：
- 保持代码示例的完整性
- 包含必要的导入语句
- 提供测试步骤和预期结果

---

## 🔗 相关文档

- [设计规格说明书](../../specs/2026-04-13-rag-llm-refactoring-spec.md) - 原始设计规格
- [MySQL 集成方案](../mysql-integration/) - 架构参考
- [RAG 系统完整文档](../../../../RAG_SYSTEM_COMPLETE_DOCUMENTATION.md) - RAG 系统技术文档

---

**最后更新：** 2026-04-14  
**文档版本：** 0.3 (全Phase细粒度拆分完成)  
**维护者：** AI Assistant
