# Phase 7: 提示词管理重构 — 总览

> **需求来源**: spec 文档 `07-prompt-management-overview.md`, `07a-prompt-data-model.md`, `07b-prompt-frontend-pages.md`, `07c-prompt-impact-analysis.md`
> **需求点数量**: 10 个
> **优先级**: P2

## 目标

重构提示词管理，实现中文说明、影响分析、测试沙箱、版本对比。

## 需求点清单

### 数据模型 (2 个) - P0 基础

| # | 需求点 | 实施文件 | 优先级 | 说明 |
|---|--------|---------|--------|------|
| 1 | PromptMetadata 模型 | `01-promptmetadata-model.md` | P0 | 新增提示词元数据表，中文字段，变量声明 |
| 2 | PromptVersion 调整 | `02-promptversion-adjustment.md` | P0 | 新增 variables_extracted, change_impact 字段 |

### 前端页面 (4 个) - P0 核心功能

| # | 需求点 | 实施文件 | 优先级 | 说明 |
|---|--------|---------|--------|------|
| 3 | 提示词列表页 | `03-prompt-list-page.md` | P0 | 中文名称 + 用途说明 + 当前版本号 + 使用状态 |
| 4 | 提示词编辑页 | `04-prompt-edit-page.md` | P0 | 内容编辑 + 变量可视化 + 影响分析面板 |
| 5 | 提示词版本对比页 | `05-prompt-version-comparison.md` | P0 | diff 可视化 + 变更摘要 |
| 6 | 提示词测试沙箱页 | `06-prompt-test-sandbox.md` | P1 | 输入变量表单 + 预览 LLM 输出 + 新旧对比 |

### 影响分析引擎 (4 个) - P1 高级功能

| # | 需求点 | 实施文件 | 优先级 | 说明 |
|---|--------|---------|--------|------|
| 7 | 影响分析引擎 | `07-impact-analysis-engine.md` | P0 | 综合分析代码引用、变量变更、配置依赖 |
| 8 | 代码引用扫描器 | `08-code-reference-scanner.md` | P0 | 扫描代码中 `prompt_manager.get_prompt(key)` 位置 |
| 9 | 变量校验器 | `09-variable-validator.md` | P0 | 校验提示词变量新增/删除/修改 |
| 10 | 配置参数依赖检测器 | `10-config-dependency-detector.md` | P1 | 检测提示词中引用的配置参数 |

## 验收标准

- [ ] 提示词列表展示中文名称和用途
- [ ] 编辑页展示变量可视化面板
- [ ] 版本对比 diff 可视化
- [ ] 测试沙箱可预览 LLM 输出
- [ ] 影响分析引擎正确扫描代码引用
- [ ] 变量校验器正确检测变量变更
- [ ] 配置参数依赖检测器正确识别依赖

## spec 07d 代码适配策略归属说明

spec 文档 `07d-prompt-code-adaptation.md` 中的需求已拆分合并到以下实施文件中：

| 07d 内容 | 归属 Plan 文件 | 说明 |
|---------|---------------|------|
| 核心问题定义（什么情况下需要改代码） | `07-impact-analysis-engine.md` | 作为影响分析的判断规则 |
| 适配策略（检测流程） | `07-impact-analysis-engine.md` | 保存提示词后的自动检测流程 |
| 影响报告格式 | `07-impact-analysis-engine.md` | 影响报告的输出格式定义 |
| 代码适配建议生成器 | `08-code-reference-scanner.md` + `09-variable-validator.md` | 扫描引用位置 + 校验变量变化后生成建议代码 |
| 降级文件自动同步 | `07-impact-analysis-engine.md` | spec 明确验收标准为"同步降级为手动"，因此实现为"检测不同步 → 提示用户手动同步"，不做自动写入 |

## 核心原则

- 提示词是代码与数据的契约，修改必须告知影响
- 系统只提供信息，不替用户做决策
- 所有提示词必须有中文名称和用途说明

---

**文档索引**: 
- 上一节: [Phase 6 总览](../phase-6/00-overview.md)
- 下一节: [01-promptmetadata-model.md](./01-promptmetadata-model.md) — 需求点 1
