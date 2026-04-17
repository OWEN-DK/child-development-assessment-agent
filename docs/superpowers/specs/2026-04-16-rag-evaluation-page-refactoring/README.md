# RAG 评估平台重构需求文档

> **文档版本**: v15.0  
> **创建日期**: 2026-04-16  
> **状态**: 第三轮审核完成，方案完整闭环  
> **关联文档**: `docs/rag_search_optimization_requirements.md`  
> **参考标准**: Arize Phoenix, LangSmith

---

## ⚠️ 核心实施原则（零兼容，必须遵守）

> **以下原则适用于本方案的所有 Phase，实施计划生成时必须严格遵守，不可偏离：**

### 🚫 绝对禁止

1. **禁止任何兼容方案** — 不写兼容代码、不写迁移脚本、不做双版本并行、不加 `@deprecated` 标记
2. **禁止后续计划** — 所有功能必须在本方案范围内给出完整需求，有后续计划的直接在本方案中补充完整需求
3. **禁止隐藏删除项** — 哪里要改、哪里要删，必须在需求文档中明确列出，实施时直接删除

### ✅ 必须做到

1. **所有修改在需求文档中列出** — 每个变更必须标注：修改位置（文件路径）、修改内容、删除的老代码
2. **老代码直接删除** — 实施计划中明确标注"删除 XXX"，不留残留
3. **需求完整闭环** — 不拆分到"后续版本"，所有需求一次性给全

---

## 📖 文档导航

本文档已按功能模块拆分为多个子文档，便于管理和维护。

### 入口文档

| 文档 | 说明 |
|------|------|
| [README.md](./README.md) | 主索引文件（入口） |
| [DOCUMENT_STRUCTURE.md](./DOCUMENT_STRUCTURE.md) | 文档结构说明 |
| [PROGRESS.md](./PROGRESS.md) | 实施进度追踪 |

### 核心文档

| 文档 | 说明 |
|------|------|
| [00-overview.md](./00-overview.md) | 项目概览：用户需求声明、项目核心规则、第一性原理分析、重构策略 |
| [01-phase-0-bug-fixes.md](./01-phase-0-bug-fixes.md) | Phase 0：核心工作流修复（书籍导入 + 批量测试 12 个根因） |
| [02-data-model.md](./02-data-model.md) | 核心数据模型：TestSet/TestCase/ConfigVersion/PromptVersion/TestReport 等 |
| [03-sse-workflow.md](./03-sse-workflow.md) | SSE 事件契约与工作流：7 种事件、断线重连、运行工作流 |
| [04-frontend-pages.md](./04-frontend-pages.md) | 前端页面设计：路由、评估报告、推荐模式面板、测试集管理 |
| [05-validation-layers.md](./05-validation-layers.md) | 6 层校验引擎：Layer 1-6 共 13 种校验的触发条件/输入/输出/规则 |
| [06-reference-metrics.md](./06-reference-metrics.md) | 参考指标体系：检索/生成/NLP/端到端四大类指标 |

### 提示词管理重构

| 文档 | 说明 |
|------|------|
| [07-prompt-management-overview.md](./07-prompt-management-overview.md) | 提示词管理重构概览：用户痛点、第一性原理、重构策略、联动关系 |
| [07a-prompt-data-model.md](./07a-prompt-data-model.md) | 数据模型重构：新增 PromptMetadata 表、中文字段、变量声明、影响分析元数据 |
| [07b-prompt-frontend-pages.md](./07b-prompt-frontend-pages.md) | 前端页面重构：列表、编辑、版本对比、测试沙箱 |
| [07c-prompt-impact-analysis.md](./07c-prompt-impact-analysis.md) | 影响分析引擎：代码引用扫描、变量校验、配置参数依赖检测 |
| [07d-prompt-code-adaptation.md](./07d-prompt-code-adaptation.md) | 代码适配策略：变量改动时如何保证与代码适配 |

### 配置管理优化

| 文档 | 说明 |
|------|------|
| [08-config-management-overview.md](./08-config-management-overview.md) | 配置管理优化概览：用户痛点、第一性原理、优化策略 |
| [08a-config-metadata.md](./08a-config-metadata.md) | 配置元数据补充：所有配置项的中文名称、用途说明、取值范围、推荐范围 |
| [08b-config-frontend-pages.md](./08b-config-frontend-pages.md) | 前端配置页重构：分组展示、实时校验、影响范围展示 |
| [08c-config-validation.md](./08c-config-validation.md) | 配置校验引擎：取值范围、推荐范围、冲突检测 |

### 阅读顺序

1. **入口**: 从 [`README.md`](./README.md) 开始，了解项目整体
2. **概览**: 阅读 [`00-overview.md`](./00-overview.md)，了解用户需求、核心规则、第一性原理
3. **实施前提**: 阅读 [`01-phase-0-bug-fixes.md`](./01-phase-0-bug-fixes.md)，修复核心工作流
4. **数据模型**: 阅读 [`02-data-model.md`](./02-data-model.md)，理解数据结构
5. **工作流**: 阅读 [`03-sse-workflow.md`](./03-sse-workflow.md)，理解 SSE 事件和运行流程
6. **前端**: 阅读 [`04-frontend-pages.md`](./04-frontend-pages.md)，了解页面设计
7. **校验引擎**: 阅读 [`05-validation-layers.md`](./05-validation-layers.md)，理解 6 层校验
8. **指标**: 阅读 [`06-reference-metrics.md`](./06-reference-metrics.md)，了解参考指标体系
9. **提示词重构**: 阅读 [`07-prompt-management-overview.md`](./07-prompt-management-overview.md)，了解提示词管理重构
10. **配置优化**: 阅读 [`08-config-management-overview.md`](./08-config-management-overview.md)，了解配置管理优化

---

## 📋 文档变更记录

| 日期 | 版本 | 变更内容 | 变更人 |
|------|------|----------|--------|
| 2026-04-16 | v1.0 | 初始版本 | AI 开发团队 |
| 2026-04-16 | v2.0 | 基于第一性原理重构，聚焦核心工作流和失败根因 | AI 开发团队 |
| 2026-04-16 | v3.0 | Brainstorming：以测试集为核心、6层校验体系、推荐模式面板 | AI 开发团队 |
| 2026-04-16 | v4.0 | 精简为纯需求文档 + 页面设计，删除 API/实施/算法伪代码/迁移/工时 | AI 开发团队 |
| 2026-04-16 | v5.0 | 恢复 6 层 13 种校验完整定义 (用户关注指标)，补充 Layer 4-6 数据流 | AI 开发团队 |
| 2026-04-16 | v6.0 | 新增用户需求声明 (禁止替用户决策/必须展示对比/必须说明原因/必须预览影响)，标记关键需求到各章节 | AI 开发团队 |
| 2026-04-16 | v7.0 | 补充参考指标体系 (检索/生成/NLP/端到端四大类)，新增 06-reference-metrics.md | AI 开发团队 |
| 2026-04-16 | v8.0 | 修复 6.1 数据流图 Layer 3 触发条件不一致；补充 5 个缺失数据模型；修复 test_set_ids 单复数；补充人工标注数据来源、分块质量评分标准、已忽略列表、导出功能、TestRun 状态枚举、草稿状态机、路由兼容性说明 | AI 开发团队 |
| 2026-04-16 | v8.1 | 新增"禁止兼容历史版本"核心原则 (项目未上线，零历史包袱)，删除路由兼容性说明中的"兼容层"表述 | AI 开发团队 |
| 2026-04-16 | v9.0 | 新增"项目核心规则"章节，引用 CLAUDE.md 及其子文档的全部核心规则 | AI 开发团队 |
| 2026-04-16 | v10.0 | 方案审核修复版：修复 7 个 CRITICAL、8 个 HIGH、12 个 MEDIUM 问题；补充用户指定的参考指标体系 (检索/生成/NLP/端到端四大类) | AI 开发团队 |
| 2026-04-16 | v10.1 | 文档拆分：按功能模块拆分为 6 个子文档 + README + DOCUMENT_STRUCTURE + PROGRESS | AI 开发团队 |
| 2026-04-16 | v11.0 | 审核修复：全部 ID 改为 UUID；ConfigChangeSetPrompt 关联表替代 JSON 数组；TestReport 6 列合并为单列；修复 Layer 3 触发条件矛盾；修正成本效果比公式；补充 heartbeat 事件；修复编号跳跃；补充导出实现方式和趋势图聚合策略；明确配置元数据存储策略 | AI 开发团队 |
| 2026-04-16 | v12.0 | 零兼容原则：删除所有兼容/迁移/后续/deprecated 表述；明确标记所有老代码删除清单（PromptABTest 模型/API/前端、OneClickOptimize 组件、PromptVersion.variables/tags/fallback 字段、A/B 测试 API 端点）；代码修改清单改为具体文件路径 |
| 2026-04-16 | v13.0 | 方案遗漏修复：补充权限策略（明确不需要 RBAC）、TestReport 创建条件规则（失败/取消时生成部分报告）、6 层校验超时与资源限制（总体 5 分钟超时、单层层超时、降级后报告状态、取消机制、并发限制）、ConfigChangeSet 原子保存与热重载时序（事务提交后发布 Redis 事件、多实例生效延迟 100ms）、QueryIntentLog 写入时机（用例执行时自动写入）、PDF 导出技术方案（weasyprint + Jinja2 模板）、A/B 影子测试报告生成逻辑（3 份报告）、IgnoredSuggestion 恢复操作行为（report/test_set 级别不同处理）、PromptMetadata 初始化策略（独立脚本、数据来源、冲突处理）、趋势图交互细节（误差线样式、多指标叠加、hover 详情）、同义查询对来源（内置 20 对 + 自动提取 + 用户维护 + SynonymQueryPair 表）、级联删除边界情况（双重级联幂等处理）、SSE 断线重连完整数据恢复流程（5 步恢复 + Redis 进度缓存）、配置冲突检测规则（10 条完整规则列表） |
| 2026-04-16 | v14.0 | 交叉校验修复：补充 TestRunResult 模型定义（断线重连降级方案 + 运行详情页数据源）、补充 SynonymQueryPair 到 02-data-model.md（原仅在 05-validation-layers.md 中定义）、数据模型总数从 16 修正为 17、修复 07a 验收标准矛盾（prompts_fallback.py 同步改为手动，删除 CI 钩子要求）、明确旧路由 /rag-evaluation 处理方式（直接删除，不保留兼容）、修复 SQLAlchemy 异步事务伪代码错误（async with session.begin() 不需要显式 commit）、PROGRESS.md Phase 1 模型创建清单同步更新为 17 个模型 |
| 2026-04-16 | v15.0 | 第三轮审核修复：PromptVersion 补充 variables_extracted 和 change_impact 字段（07a 定义但 02 缺失）、ConfigVersion 新增 version_number 数字排序字段（解决 version_label 字符串排序不准确问题）、Bad Case 定义明确化（hit_at_5=0 为 Bad Case，Layer 3 失败类型是 LLM 语义分析结果不等于 Bad Case 定义）、validation_results status 枚举值完整定义（completed/degraded/timeout/cancelled/skipped）、case_result SSE 事件 status 字段值明确为 passed/failed、TestReport tuning_suggestion_summary 格式修正为同时包含 config 和 prompt 建议统计、PROGRESS.md SSE 事件数量从 9 修正为 10、Layer 3 输入数据来源明确化（TestRunResult.query/matched_doc_ids + TestCase.expected_document_ids） | AI 开发团队 |

---

## ✅ 文档完成度

| 章节 | 状态 | 所在子文档 |
|------|------|-----------|
| ⚠️ 用户需求声明 | ✅ 完成 | 00-overview.md |
| ⚠️ 项目核心规则 | ✅ 完成 | 00-overview.md |
| 1. 第一性原理分析 | ✅ 完成 | 00-overview.md |
| 2.0 Phase 0 修复需求 | ✅ 完成 | 01-phase-0-bug-fixes.md |
| 2.1 重构策略 | ✅ 完成 | 00-overview.md |
| 3.2 分层递进架构 | ✅ 完成 | 05-validation-layers.md |
| 3.3 校验层定义 | ✅ 完成 | 05-validation-layers.md |
| 3.4 数据模型 | ✅ 完成 | 02-data-model.md |
| 3.5 运行工作流 | ✅ 完成 | 03-sse-workflow.md |
| 3.5.1 SSE 事件定义 | ✅ 完成 | 03-sse-workflow.md |
| 3.6 前端路由 | ✅ 完成 | 04-frontend-pages.md |
| 4. 页面设计 | ✅ 完成 | 04-frontend-pages.md |
| 5. 校验定义 (Layer 1-6) | ✅ 完成 | 05-validation-layers.md |
| 6.1 数据流设计 | ✅ 完成 | 05-validation-layers.md |
| 6.2 报告状态机 | ✅ 完成 | 02-data-model.md |
| 7. 术语表 | ✅ 完成 | 00-overview.md |
| 8. 参考指标体系 | ✅ 完成 | 06-reference-metrics.md |

---

## 🔧 v10.0 审核修复摘要

| 问题级别 | 修复数量 | 核心修复内容 |
|---------|---------|-------------|
| CRITICAL | 7 | 循环 FK 解除、TestSetCase 中间表、ConfigVersion JSON 快照、PromptVersion VARCHAR 版本、ConfigChangeSet JSON 数组、Embedding 校验方法论修正、分块质量评分公式修正 |
| HIGH | 8 | SSE 事件拆分 (test_completed + report_ready)、case_result 改为 hit@k、ConfigChangeSet 事务边界、三步审查面板、SSE 断线重连、废弃 OneClickOptimize、Layer 1 自适应建议、成本效果比公式 |
| MEDIUM | 12 | Bad Case 分层抽样、LLM 失败类型/根因扩充、文档时效性分类、A/B 分层抽样+显著性检验、历史对比算法定义、错误模式多维交叉分组、面板 Drawer 适配、对比视图自定义值、趋势图时间轴、配置回滚流程、运行取消按钮、忽略列表双级别 |

---

## 🔧 v11.0 审核修复摘要 (2026-04-16)

| 问题级别 | 修复数量 | 核心修复内容 |
|---------|---------|-------------|
| CRITICAL | 5 | 全部 ID 改为 UUID (C4)、ConfigChangeSetPrompt 关联表替代 JSON 数组 (C3)、TestReport 6 列合并为单列 (H1)、ConfigVersion version_label 语义化 (H2)、编号跳跃修复 (C5) |
| HIGH | 3 | Layer 3 触发条件矛盾修复 (H4)、成本效果比公式修正+示例 (H3)、heartbeat 事件补充 (H5) |
| MEDIUM | 3 | 导出功能实现方式明确 (M2)、趋势图聚合策略定义 (M3)、配置元数据存储策略明确 (M4) |

---

**最后更新:** 2026-04-16  
**文档版本:** v12.0 (零兼容原则修复完成)  
**维护者:** AI Assistant
