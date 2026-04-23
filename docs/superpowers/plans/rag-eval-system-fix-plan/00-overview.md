# RAG 评估系统修复方案 - 项目概览

**日期**: 2026-04-18  
**状态**: 待实施  
**版本**: v1.0  

---

## 一、方案总览

### 1.1 修复范围

本方案涵盖 **12 大领域**，包含原有修复需求和新增功能需求：
| 优先级 | 领域 | 问题描述 | 工作量 | 详细方案 |
|--------|------|----------|--------|----------|
| **P0** | 提示词系统 Bug | `config_health_service.py` 导入错误模块 | 0.5h | [01-p0-bug-fixes.md](./01-p0-bug-fixes.md) |
| **P0** | RAG 流水线接入 | 删除硬编码链路 → 直接接入 `PipelineOrchestrator` 声明式 | 6h | [01-p0-bug-fixes.md](./01-p0-bug-fixes.md) |
| **P0** | 配置系统重构 | 消除重复混乱 + LLM 全量热加载 + 复用现有 EventBus + 删除废弃字段 + 竞态保护 + 迁移备份 | 19h | [06-config-system-refactor.md](./06-config-system-refactor.md) |
| **P1** | 提示词迁移 | 3 处绕过 `PromptManager` 的直接导入（复用现有能力，保留 `prompts_fallback.py` 作为兜底） | 2h | [02-p1-prompt-migration.md](./02-p1-prompt-migration.md) |
| **P1** | 12 种认知维度矩阵 | `TestCaseDraftGenerator` 实现 | 3h | [02-p1-prompt-migration.md](./02-p1-prompt-migration.md) |
| **P1** | 提示词页面重构 | 两套页面合并 + A/B 测试删除 + 路由/API 对齐 + 功能增强 | 6.5h | [07-prompt-management-refactor.md](./07-prompt-management-refactor.md) |
| **P2** | 前端 Tab 重构 | 草稿/测试用例/测试集/报告 Tab 切换 + 前后端工作流约束 | 8h | [03-frontend-tab-refactor.md](./03-frontend-tab-refactor.md) |
| **P2** | Phase 0 根因修复 | 书籍导入 5 个 + 批量测试 7 个 + LLM 工厂签名 1 个根因 | 5h | [04-phase0-root-cause-fixes.md](./04-phase0-root-cause-fixes.md) |
| **P1** | 【新增】数据模型增强 | 实现TestReport、TuningSuggestionRecord、IntentAnnotation三个核心模型（修正外键+索引） | 20h | [08-data-model-enhancement.md](./08-data-model-enhancement.md) |
| **P1** | 【新增】6层校验引擎 | 实现6层递进式诊断校验能力，自动生成调优建议（已细化每层设计+全局超时+Prompt动态加载+并行优化） | 183h | [09-validation-engine.md](./09-validation-engine.md) |
| **P2** | 【新增】评估报告高级功能 | 实现6层校验结果展示、调优建议交互、趋势追踪、报告导出 | 72h | [10-report-enhancement.md](./10-report-enhancement.md) |
| **P2** | 【新增】调优交互完善 | 实现Diff对比展示、影响分析预览、版本回滚、操作审计 | 32h | [11-tuning-interaction.md](./11-tuning-interaction.md) |
**总工作量**: 约 **356h**（约45人天，预留15%缓冲后约90-110人天）

### 1.2 前端新需求核心原则

```
工作流程强制约束：
书籍/JSON 导入 → 草稿审核 → 通过后进入测试用例库 → 测试集管理只能引用已有测试用例

禁止绕过：
❌ 测试集管理不能直接创建测试用例
❌ 测试集管理不能直接导入书籍/JSON
✅ 所有数据必须先经过草稿审核流程
```

### 1.3 文档索引

| 文档 | 内容 |
|------|------|
| [00-overview.md](./00-overview.md) | 项目概览、修复范围、核心原则（本文档） |
| [01-p0-bug-fixes.md](./01-p0-bug-fixes.md) | P0 级别修复：提示词 Bug + RAG 流水线接入 |
| [02-p1-prompt-migration.md](./02-p1-prompt-migration.md) | P1 级别修复：提示词迁移 + 12 种认知维度矩阵 |
| [03-frontend-tab-refactor.md](./03-frontend-tab-refactor.md) | P2 前端 Tab 重构：四页面设计 + 工作流约束 |
| [04-phase0-root-cause-fixes.md](./04-phase0-root-cause-fixes.md) | Phase 0 根因修复：12 个根因详细修复方案 |
| [05-implementation-plan.md](./05-implementation-plan.md) | 实施顺序、风险、验收清单、后续优化 |
| [06-config-system-refactor.md](./06-config-system-refactor.md) | P0 配置系统重构：消除重复 + 全量热加载 + 凭证统一管理 |
| [07-prompt-management-refactor.md](./07-prompt-management-refactor.md) | P1 提示词页面重构：两套页面合并 + A/B 测试删除 + 路由/API 对齐 |

---

## 二、实施前提

### 2.1 技术栈要求

- **后端**: Python 3.13, FastAPI, SQLAlchemy 2.0
- **前端**: React 19, TypeScript 5.3, Ant Design 6
- **编排**: LangGraph 1.1, PipelineOrchestrator（已实现但未接入）
- **提示词**: PromptManager（已实现，已内置降级逻辑，部分代码绕过）

### 2.2 现有系统状态

| 模块 | 状态 | 说明 |
|------|------|------|
| 配置系统三层架构 | ✅ 完整 | core/modules/rules 拆分，多重继承聚合 |
| PipelineOrchestrator | ⚠️ 已建未用 | YAML + 编排器 + 10 个步骤类已实现，但未接入调用链路 |
| PromptManager | ⚠️ 部分使用 | 核心类已实现，**已内置降级/缓存/变量渲染**，但 3 处代码绕过直接导入 fallback |
| EventBus | ✅ 完整 | `ConfigChangedEvent` 已定义，支持 Redis Pub/Sub |
| 数据模型 | ✅ 完整 | TestCase/TestSet/SourceDocument 等 ORM + Schema |
| 前端页面 | ⚠️ 需重构 | 现有页面分散，缺少 Tab 聚合和工作流约束 |

### 2.3 审核修正记录

**审核日期**: 2026-04-18  
**审核人**: AI Assistant

| # | 修正项 | 原方案 | 修正后 | 原因 |
|---|--------|--------|--------|------|
| 1 | PipelineOrchestrator 签名 | 假设接收 `PipelineContext` 对象 | 实际 `execute(query, age, limit) -> list` | 读取实际代码后发现不匹配 |
| 2 | PromptLoader | 新建单例类 | 删除，复用现有 `PromptManager` | PromptManager 已内置降级/缓存/渲染 |
| 3 | ConfigChangedEvent | 新建事件类 | 删除，复用现有 `config/core/events.py` | 系统已有 EventBus 和事件定义 |
| 4 | CognitiveDimension 位置 | `service/rag_test/` | `schemas/cognitive_dimension.py` | 违反 CLAUDE.md 实体类规范 |
| 5 | 工作流约束 | 仅前端限制 | 前端 + 后端双重验证 | 用户可直接调用 API 绕过前端 |
| 6 | 工作量估算 | 30h | 40h | 适配实际代码 + 集成测试 + 后端验证 |
| 7 | 零迁移原则 | 保留向后兼容/降级逻辑 | 直接删除旧代码 | 遵循 CLAUDE.md 第 9 条（提示词 fallback 除外，保留类似 .env） |

---

## 三、核心设计原则

### 3.1 用户画像

- **用户是懂技术的**（配置管理、提示词管理、回溯测试的使用者都有技术背景）
- **不是小白用户**，不需要"一键优化"式的傻瓜操作

### 3.2 禁止事项

1. **禁止替用户做决策** — 推荐只是参考，不能自动应用配置
2. **禁止隐藏决策依据** — 每个推荐必须解释"为什么改"
3. **禁止跳过对比环节** — 用户必须能看到改动前后的差异
4. **禁止省略影响分析** — 用户需要知道"改了会有什么后果"
5. **禁止兼容历史版本** — 项目未上线，不存在旧数据/旧接口/旧页面迁移需求

### 3.3 必须事项

1. **必须展示前后对比** — 配置值 diff、提示词内容 diff
2. **必须说明改动原因** — 触发条件、指标短板、Bad Case 分析
3. **必须预览改动影响** — 预期指标变化、风险警告、历史参考
4. **必须让用户手动确认** — 采纳 → 审查 → 保存为新版本，三步分离
5. **必须支持回溯** — 每次修改留版本记录，可回滚

### 3.4 核心原则

```
系统角色：辅助决策者（提供信息、分析、建议）
用户角色：最终决策者（审查、判断、执行）

错误设计：检测到问题 → 自动应用推荐配置
正确设计：检测到问题 → 展示原因+对比+影响 → 用户决定是否采纳
```

---

## 四、快速导航

### 按优先级查看

- 🔴 **P0 紧急修复** → [01-p0-bug-fixes.md](./01-p0-bug-fixes.md) + [06-config-system-refactor.md](./06-config-system-refactor.md)
- 🟡 **P1 重要优化** → [02-p1-prompt-migration.md](./02-p1-prompt-migration.md) + [07-prompt-management-refactor.md](./07-prompt-management-refactor.md)
- 🟢 **P2 功能增强** → [03-frontend-tab-refactor.md](./03-frontend-tab-refactor.md) + [04-phase0-root-cause-fixes.md](./04-phase0-root-cause-fixes.md)

### 按实施阶段查看

- **阶段 1**：核心 Bug 修复 → [01-p0-bug-fixes.md](./01-p0-bug-fixes.md) + [04-phase0-root-cause-fixes.md](./04-phase0-root-cause-fixes.md)
- **阶段 2**：RAG 流水线接入 → [01-p0-bug-fixes.md](./01-p0-bug-fixes.md)
- **阶段 3**：配置系统重构 → [06-config-system-refactor.md](./06-config-system-refactor.md)
- **阶段 4**：提示词迁移 → [02-p1-prompt-migration.md](./02-p1-prompt-migration.md)
- **阶段 5**：认知维度矩阵 → [02-p1-prompt-migration.md](./02-p1-prompt-migration.md)
- **阶段 6**：提示词页面重构 → [07-prompt-management-refactor.md](./07-prompt-management-refactor.md)
- **阶段 7**：前端 Tab 重构 → [03-frontend-tab-refactor.md](./03-frontend-tab-refactor.md)

### 验收与风险

- **验收清单** → [05-implementation-plan.md](./05-implementation-plan.md)
- **风险分析** → [05-implementation-plan.md](./05-implementation-plan.md)
- **后续优化** → [05-implementation-plan.md](./05-implementation-plan.md)

---

**方案制定完成，等待实施指令**。
