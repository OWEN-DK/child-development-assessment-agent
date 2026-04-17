# RAG 评估与 LLM 多模型提供商重构 - 索引

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 完成六大系统升级：RAG 评估工作流重塑、LLM 多提供商扩展、参数全量热配置、硬编码提示词收拢、简化版 LLM 调用追踪、智能调参建议引擎。

**Architecture:**
- LLM 多提供商工厂：支持 DashScope/OpenAI/Anthropic/DeepSeek/Ollama，统一 LangChain/LlamaIndex 适配
- 全局凭证与场景参数分离：一次配置 API Key，各场景独立控制超参数
- 热更新机制：EventBus 驱动，零停机实例重建，配置校验层保护
- 测试集核心工作流：TestSet → TestCase → TestRun → EvaluationReport 严格层级
- 简化版 Langfuse 追踪：Trace/Span 层级树，全量记录输入输出与调用参数
- 智能调参引擎：规则引擎 + 历史对比 + LLM 诊断三层递进架构

**Tech Stack:** LangChain, LlamaIndex, FastAPI, React 19, MySQL 5.7, Redis 7.0, Chroma, LangGraph, weasyprint

**方案状态:** 🚧 方案构建中

---

## 📁 文档结构

### 核心文档
- **[README.md](./README.md)** - 主索引（入口）
- **[PROGRESS.md](./PROGRESS.md)** - 📊 进度追踪
- **[00-overview.md](./00-overview.md)** - 项目概览、文件结构变更、架构说明

#### Phase 1: LLM 多提供商 + 热配置
- **[01-phase-1-00-overview.md](./01-phase-1-00-overview.md)** - Phase 1 总览与目标
- **[01-phase-1-01-config-layer.md](./01-phase-1-01-config-layer.md)** - 配置层设计与参数模型
- **[01-phase-1-02-factory-refactor.md](./01-phase-1-02-factory-refactor.md)** - 工厂重构与多提供商适配
- **[01-phase-1-03-hot-reload.md](./01-phase-1-03-hot-reload.md)** - 热更新机制与事件总线集成
- **[01-phase-1-04-call-sites.md](./01-phase-1-04-call-sites.md)** - 调用点改造与向后兼容
- **[01-phase-1-05-dependencies.md](./01-phase-1-05-dependencies.md)** - 依赖升级与兼容性处理
- **[01-phase-1-llm-providers.md](./01-phase-1-llm-providers.md)** - Phase 1 汇总文档

#### Phase 2A: RAG 评估工作流重塑
- **[02-phase-2a-00-overview.md](./02-phase-2a-00-overview.md)** - Phase 2A 总览与目标
- **[02-phase-2a-01-data-model.md](./02-phase-2a-01-data-model.md)** - 数据模型设计与数据库迁移
- **[02-phase-2a-02-execution-path.md](./02-phase-2a-02-execution-path.md)** - 执行路径与核心逻辑实现
- **[02-phase-2a-03-report-lifecycle.md](./02-phase-2a-03-report-lifecycle.md)** - 报告生命周期管理
- **[02-phase-2a-04-test-case-generation.md](./02-phase-2a-04-test-case-generation.md)** - 测试用例自动生成与审核
- **[02-phase-2a-05-frontend-ui.md](./02-phase-2a-05-frontend-ui.md)** - 前端界面与交互设计
- **[02-phase-2a-rag-workflow.md](./02-phase-2a-rag-workflow.md)** - Phase 2A 汇总文档

#### Phase 2B: 提示词/配置收拢
- **[03-phase-2b-00-overview.md](./03-phase-2b-00-overview.md)** - Phase 2B 总览与目标
- **[03-phase-2b-01-prompt-scan.md](./03-phase-2b-01-prompt-scan.md)** - 提示词扫描与盘点
- **[03-phase-2b-02-prompt-migration.md](./03-phase-2b-02-prompt-migration.md)** - 提示词迁移与接入
- **[03-phase-2b-03-prompt-validation.md](./03-phase-2b-03-prompt-validation.md)** - 提示词校验与测试
- **[03-phase-2b-04-config-scan.md](./03-phase-2b-04-config-scan.md)** - 配置扫描与盘点
- **[03-phase-2b-05-config-migration.md](./03-phase-2b-05-config-migration.md)** - 配置迁移与接入
- **[03-phase-2b-06-magic-value-cleanup.md](./03-phase-2b-06-magic-value-cleanup.md)** - 魔法值清理与重构
- **[03-phase-2b-07-compatibility.md](./03-phase-2b-07-compatibility.md)** - 兼容性与降级处理
- **[03-phase-2b-prompt-config-cleanup.md](./03-phase-2b-prompt-config-cleanup.md)** - Phase 2B 汇总文档

#### Phase 2C: 智能调参建议引擎
- **[04-phase-2c-00-overview.md](./04-phase-2c-00-overview.md)** - Phase 2C 总览与目标
- **[04-phase-2c-01-rule-engine-design.md](./04-phase-2c-01-rule-engine-design.md)** - 规则引擎设计与实现
- **[04-phase-2c-02-rule-library.md](./04-phase-2c-02-rule-library.md)** - 规则库与阈值配置
- **[04-phase-2c-03-historical-data.md](./04-phase-2c-03-historical-data.md)** - 历史数据层实现
- **[04-phase-2c-04-comparison-algorithm.md](./04-phase-2c-04-comparison-algorithm.md)** - 对比算法与趋势分析
- **[04-phase-2c-05-llm-diagnosis.md](./04-phase-2c-05-llm-diagnosis.md)** - LLM诊断层实现
- **[04-phase-2c-06-suggestion-closed-loop.md](./04-phase-2c-06-suggestion-closed-loop.md)** - 建议落地与闭环
- **[04-phase-2c-07-frontend-ui.md](./04-phase-2c-07-frontend-ui.md)** - 前端UI与交互
- **[04-phase-2c-tuning-engine.md](./04-phase-2c-tuning-engine.md)** - Phase 2C 汇总文档

#### Phase 3: LLM 调用追踪
- **[05-phase-3-00-overview.md](./05-phase-3-00-overview.md)** - Phase 3 总览与目标
- **[05-phase-3-01-trace-model.md](./05-phase-3-01-trace-model.md)** - Trace/Span数据模型
- **[05-phase-3-02-storage-design.md](./05-phase-3-02-storage-design.md)** - 存储设计与优化
- **[05-phase-3-03-instrumentation.md](./05-phase-3-03-instrumentation.md)** - 埋点规范与集成
- **[05-phase-3-04-data-processing.md](./05-phase-3-04-data-processing.md)** - 数据上报与处理
- **[05-phase-3-05-dashboard.md](./05-phase-3-05-dashboard.md)** - 前端仪表盘实现
- **[05-phase-3-06-trace-details.md](./05-phase-3-06-trace-details.md)** - 链路详情与分析
- **[05-phase-3-07-alerting.md](./05-phase-3-07-alerting.md)** - 告警与监控配置
- **[05-phase-3-llm-tracing.md](./05-phase-3-llm-tracing.md)** - Phase 3 汇总文档

### 附录文档
- **[appendix-a-database-migration.md](./appendix-a-database-migration.md)** - 数据库迁移清单
- **[appendix-b-api-reference.md](./appendix-b-api-reference.md)** - API 接口变更参考
- **[appendix-c-risk-control.md](./appendix-c-risk-control.md)** - 风险控制与回滚策略
- **[appendix-d-verification-report.md](./appendix-d-verification-report.md)** - 验证与调整报告
- **[DOCUMENT_STRUCTURE.md](./DOCUMENT_STRUCTURE.md)** - 文档结构说明

---

## 📊 实施进度

| Phase | 周期 | 方案状态 | 实施状态 | 文档链接 |
|-------|------|---------|---------|---------|
| **Phase 1** | 4 天 | ✅ 已完成 | 🟢 已完成 100% | [LLM 多提供商 + 热配置](./01-phase-1-llm-providers.md) |
| **Phase 2A** | 5 天 | ✅ 已完成 | 🟢 已完成 100% | [RAG 评估工作流重塑](./02-phase-2a-rag-workflow.md) |
| **Phase 2B** | 5 天 | ✅ 已完成 | ⚪ 待实施 0% | [提示词/配置收拢](./03-phase-2b-prompt-config-cleanup.md) |
| **Phase 2C** | 4 天 | ✅ 已完成 | ⚪ 待实施 0% | [智能调参建议引擎](./04-phase-2c-tuning-engine.md) |
| **Phase 3** | 3 天 | ✅ 已完成 | ⚪ 待实施 0% | [LLM 调用追踪](./05-phase-3-llm-tracing.md) |

**总周期：** 约 21 天  
**方案构建：** ✅ 已完成（100%）  
**实施进度：** 🟡 45%（Phase 1 完成 100%，Phase 2A 完成 100%）  
**验证状态：** ⚪ 待验证  
**文档版本：** 1.2 (Phase 2A 完成)

---

## 🎯 六大升级目标

| # | 目标 | 所属 Phase | 预期效果 |
|---|------|-----------|---------|
| 1 | RAG 评估工作流重塑 | Phase 2A | 严格以测试集为核心，支持多集批量执行与报告管理 |
| 2 | LLM 多提供商扩展 | Phase 1 | 支持 5 大提供商，解耦全局凭证与场景参数 |
| 3 | LLM 参数全量热配置 | Phase 1 | 零停机热更新，配置校验层保护 |
| 4 | 硬编码提示词/配置收拢 | Phase 2B | 统一接入 PromptManager/ConfigManager，消除魔法值 |
| 5 | 简化版 LLM 调用追踪 | Phase 3 | Trace/Span 层级树，全量记录输入输出 |
| 6 | 智能调参建议引擎 | Phase 2C | 三层诊断，自动给出可操作参数优化建议 |

---

## ⚠️ 强制规则

> **【必读】** 所有请求和操作都必须参考项目根目录下的 `AGENTS.md` 与 `CLAUDE.md`。
> - 实施任何改动前，必须先阅读并理解这两个文档中的架构规范、代码约定和维护规则
> - 任何结构性改动（新增/删除文件、调整模块职责、变更 API 等）必须同步更新 `AGENTS.md` 和 `CLAUDE.md`
> - 禁止违反文档中定义的核心维护规则

---

## ⚠️ 重要说明

### 参考文档
- **设计规格说明书**: [specs/2026-04-13-rag-llm-refactoring-spec.md](../../specs/2026-04-13-rag-llm-refactoring-spec.md)
- **MySQL 集成方案**: [plans/mysql-integration/](../mysql-integration/) (架构参考)
- **RAG 系统文档**: [RAG_SYSTEM_COMPLETE_DOCUMENTATION.md](../../../../RAG_SYSTEM_COMPLETE_DOCUMENTATION.md)

### 实施原则
1. **分阶段递进**：Phase 2 拆分为 2A/2B/2C 降低单次变更风险
2. **向后兼容**：关键 API 保持签名不变，内部实现平滑迁移
3. **降级保护**：PromptManager 不可用时使用 fallback 提示词
4. **数据可追溯**：测试报告持久化保存，支持删除与导出

---

## 📖 使用指南

1. **按顺序实施**：建议按照 Phase 1 → Phase 2A → Phase 2B → Phase 2C → Phase 3 的顺序执行
2. **独立文档**：每个 Phase 都是独立的 Markdown 文件，可以单独打开和编辑
3. **任务追踪**：每个 Task 使用 checkbox (`- [ ]`) 语法，方便追踪进度
4. **代码示例**：所有代码示例都包含完整的导入和上下文，可直接复制使用

---

## 🔗 相关文档

### 核心参考
- **[设计规格说明书](../../specs/2026-04-13-rag-llm-refactoring-spec.md)** - 六大升级的完整设计规格
- **[MySQL 集成方案](../mysql-integration/)** - 基础设施参考（已完成）
- **[RAG 系统完整文档](../../../../RAG_SYSTEM_COMPLETE_DOCUMENTATION.md)** - RAG 系统技术文档

### 项目文档
- [AGENTS.md](../../../../AGENTS.md) - Agent 系统架构文档
- [CLAUDE.md](../../../../CLAUDE.md) - 项目指南和代码规范

---

**最后更新：** 2026-04-14  
**文档版本：** 1.0 (全部方案完成)  
**状态：** ✅ 方案已全部完成，待实施
