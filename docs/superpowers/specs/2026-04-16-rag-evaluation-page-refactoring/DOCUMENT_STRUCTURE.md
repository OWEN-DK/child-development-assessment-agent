# 文档结构说明

## 📁 文件组织

本文档将 RAG 评估平台重构需求拆分为多个独立模块，便于管理和维护。

### 核心文档结构

```
2026-04-16-rag-evaluation-page-refactoring/
├── README.md                              # 主索引文件（入口）
├── PROGRESS.md                            # 进度追踪
├── DOCUMENT_STRUCTURE.md                  # 本文档
│
├── 00-overview.md                         # 项目概览
│   ├── 用户需求声明 (禁止事项/必须事项/核心原则)
│   ├── 项目核心规则 (CLAUDE.md 引用)
│   ├── 第一性原理分析 (用户核心任务/工作流断裂/根因定位)
│   └── 重构策略 (核心原则/信息架构)
│
├── 01-phase-0-bug-fixes.md               # Phase 0: 核心工作流修复
│   ├── 书籍导入修复 (5 个根因)
│   └── 批量测试修复 (7 个根因)
│
├── 02-data-model.md                       # 核心数据模型
│   ├── TestSet / TestSetCase / TestCase
│   ├── ConfigVersion / PromptVersion / ConfigChangeSet / ConfigChangeSetPrompt
│   ├── TestReport / TuningSuggestionRecord / PromptSuggestionRecord
│   ├── TestRun / TestCaseDraft / IntentAnnotation
│   ├── 状态枚举 (TestRun / TestCaseDraft)
│   └── 状态机 (TestReport / TestCaseDraft)
│
├── 03-sse-workflow.md                     # SSE 事件与工作流
│   ├── 测试集运行工作流
│   ├── SSE 事件定义 (9 种事件)
│   ├── 前端展示映射
│   └── 断线重连机制
│
├── 04-frontend-pages.md                   # 前端页面设计
│   ├── 前端路由 (/rag-eval/*)
│   ├── 评估报告页 (核心页面)
│   ├── 推荐模式面板 (推荐/向导/专家三种模式)
│   ├── 审查面板 (采纳→审查→保存三步分离)
│   ├── 对比视图 (配置对比/提示词对比/自定义值)
│   ├── 测试集列表/详情页
│   ├── 草稿审核页
│   ├── 运行历史/详情页
│   ├── 趋势追踪
│   ├── 配置版本回滚
│   └── 导出功能 (PDF/CSV/JSON)
│
├── 05-validation-layers.md                # 6 层校验引擎
│   ├── Layer 1: 规则引擎 (自适应步长 + 冲突检测)
│   ├── Layer 2: 历史对比 (差分对比 + 失败模式匹配)
│   ├── Layer 3: LLM 诊断 (7 种失败类型 + 8 种根因 + 降级策略)
│   ├── Layer 4: 数据质量 (Golden 覆盖 + 分块质量 + 文档时效)
│   ├── Layer 5: 检索链路 (Embedding 校验 + 意图识别 + 错误模式分组)
│   └── Layer 6: 验证保障 (回归检测 + 交叉验证 + 成本效果 + A/B 影子)
│
├── 06-reference-metrics.md                # 参考指标体系
│   ├── 检索阶段核心指标 (Precision/Recall/F1/MRR/NDCG/Context Relevance)
│   ├── 生成阶段核心指标 (Faithfulness/Answer Relevance/Completeness/Correctness)
│   ├── 传统 NLP 辅助指标 (BLEU/ROUGE/BERTScore)
│   └── 端到端评估指标 (Answer Correctness/RAGAS Score/人工评估)
│
├── 07-prompt-management-overview.md       # 提示词管理重构概览
│   ├── 用户痛点分析
│   ├── 第一性原理分析
│   ├── 重构策略
│   └── 与现有系统联动关系
│
├── 07a-prompt-data-model.md               # 提示词数据模型重构
│   ├── 现有模型分析
│   ├── 新增 PromptMetadata 模型
│   ├── PromptVersion 调整
│   ├── 初始化数据
│   └── 数据库 DDL
│
├── 07b-prompt-frontend-pages.md           # 提示词前端页面重构
│   ├── 前端路由
│   ├── 列表页设计
│   ├── 编辑页设计
│   ├── 版本管理页
│   ├── 测试沙箱页
│   └── API 端点
│
├── 07c-prompt-impact-analysis.md          # 提示词影响分析引擎
│   ├── 影响分析维度
│   ├── 代码引用扫描器
│   ├── 变量校验器
│   ├── 配置参数依赖检测器
│   └── 影响分析 API
│
├── 07d-prompt-code-adaptation.md          # 提示词代码适配策略
│   ├── 核心问题定义
│   ├── 适配策略
│   ├── 影响报告格式
│   ├── 代码适配建议生成器
│   └── 降级文件自动同步
│
├── 08-config-management-overview.md       # 配置管理优化概览
│   ├── 用户痛点分析
│   ├── 第一性原理分析
│   └── 优化策略
│
├── 08a-config-metadata.md                 # 配置元数据补充
│   ├── 现有配置分析
│   ├── 元数据模型扩展
│   └── 完整配置元数据清单（所有配置项的中文名称、用途说明、取值范围）
│
├── 08b-config-frontend-pages.md           # 前端配置页重构
│   ├── 前端路由
│   ├── 配置主页（分组卡片）
│   ├── 分类配置页
│   ├── 实时校验
│   ├── 影响范围展示
│   └── 配置版本管理
│
├── 08c-config-validation.md               # 配置校验引擎
│   ├── 校验层级设计
│   ├── 类型校验
│   ├── 范围校验
│   ├── 推荐范围警告
│   └── 冲突检测
│
└── 原文档备份
    └── 2026-04-16-rag-evaluation-page-refactoring-design.md  # v10.0 完整原文档
```

### 文档拆分策略

采用"总览 + 功能模块"的分层结构，每个模块独立成文件：

| 模块 | 文件 | 说明 |
|------|------|------|
| 项目概览 | `00-overview.md` | 用户需求声明、项目核心规则、第一性原理分析、重构策略 |
| Phase 0 修复 | `01-phase-0-bug-fixes.md` | 书籍导入 5 个根因 + 批量测试 7 个根因的修复需求与验收标准 |
| 数据模型 | `02-data-model.md` | 全部 13 个数据模型定义（主键统一 UUID）、状态枚举、状态机 |
| SSE 工作流 | `03-sse-workflow.md` | 运行工作流、9 种 SSE 事件、前端映射、断线重连 |
| 前端页面 | `04-frontend-pages.md` | 路由、评估报告、推荐模式面板、审查面板、对比视图、各列表页 |
| 校验引擎 | `05-validation-layers.md` | 6 层 13 种校验的触发条件/输入/输出/规则/降级策略 |
| 参考指标 | `06-reference-metrics.md` | 用户指定的四大类指标体系及系统落地 |
| 提示词重构概览 | `07-prompt-management-overview.md` | 提示词管理重构需求、用户痛点、重构策略、联动关系 |
| 提示词数据模型 | `07a-prompt-data-model.md` | PromptMetadata 模型、中文字段、变量声明、DDL |
| 提示词前端页面 | `07b-prompt-frontend-pages.md` | 列表、编辑、版本对比、测试沙箱页面设计 |
| 提示词影响分析 | `07c-prompt-impact-analysis.md` | 代码引用扫描、变量校验、配置依赖检测 |
| 提示词代码适配 | `07d-prompt-code-adaptation.md` | 变量改动时如何保证与代码适配的策略 |
| 配置优化概览 | `08-config-management-overview.md` | 配置管理优化需求、用户痛点、优化策略 |
| 配置元数据 | `08a-config-metadata.md` | 所有配置项的中文名称、用途说明、取值范围、推荐范围 |
| 配置前端页面 | `08b-config-frontend-pages.md` | 分组展示、实时校验、影响范围展示 |
| 配置校验引擎 | `08c-config-validation.md` | 取值范围、推荐范围、冲突检测 |

---

## 📖 使用指南

### 阅读顺序

1. **入口**: 从 [`README.md`](./README.md) 开始，了解项目整体
2. **概览**: 阅读 [`00-overview.md`](./00-overview.md)，了解用户需求、核心规则、第一性原理
3. **实施前提**: 阅读 [`01-phase-0-bug-fixes.md`](./01-phase-0-bug-fixes.md)，修复核心工作流
4. **数据模型**: 阅读 [`02-data-model.md`](./02-data-model.md)，理解数据结构
5. **工作流**: 阅读 [`03-sse-workflow.md`](./03-sse-workflow.md)，理解 SSE 事件和运行流程
6. **前端**: 阅读 [`04-frontend-pages.md`](./04-frontend-pages.md)，了解页面设计
7. **校验引擎**: 阅读 [`05-validation-layers.md`](./05-validation-layers.md)，理解 6 层校验
8. **指标**: 阅读 [`06-reference-metrics.md`](./06-reference-metrics.md)，了解参考指标体系

### 实施顺序

1. **Phase 0**: 修复核心工作流 (书籍导入 + 批量测试)
2. **Phase 1**: 创建数据模型 + 数据库表
3. **Phase 2**: 实现 SSE 工作流 + 测试集运行
4. **Phase 3**: 实现前端页面 (测试集管理 → 运行历史 → 评估报告)
5. **Phase 4**: 实现 6 层校验引擎 (Layer 1-6)
6. **Phase 5**: 实现推荐模式面板 + 配置/提示词编辑
7. **Phase 6**: 实现趋势追踪 + 导出功能

---

## 🔧 文档维护

### 添加新内容

如需补充某个模块的详细需求，可以：

1. 创建新的文件，如 `07-export-functionality.md`
2. 在 `README.md` 中更新链接
3. 在 `DOCUMENT_STRUCTURE.md` 中更新结构说明

### 更新现有内容

直接编辑对应的模块文件即可。所有修改应：
- 保持与原文档的一致性
- 包含必要的代码示例
- 提供验收标准

---

**最后更新:** 2026-04-16  
**文档版本:** v12.0  
**维护者:** AI Assistant
