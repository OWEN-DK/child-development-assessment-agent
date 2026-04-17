# RAG+LLM 重构项目概览

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 重构现有RAG与LLM调用架构，实现多提供商支持、热配置、智能调参与全链路追踪，提升系统灵活性与可观测性。

**Architecture:** 采用分层抽象架构，底层实现多LLM提供商适配，中间层提供热配置与路由能力，上层集成智能调参与链路追踪，保障业务代码无感知升级。

**Tech Stack:** Python 3.11, LangChain, LlamaIndex, FastAPI, SQLAlchemy, React 19, TypeScript

---

## 🎯 项目背景与目标

### 背景
现有系统存在以下痛点：
1. LLM 提供商绑定严重，仅支持 DashScope，无法满足多场景/多成本需求
2. 配置变更需重启服务，无法实现零停机热更新
3. 提示词与配置硬编码遍布代码库，维护成本高
4. RAG 评估工作流不完整，缺乏智能调参能力
5. LLM 调用无全链路追踪，问题排查困难

### 核心目标
1. ✅ 支持5+主流LLM提供商（DashScope、OpenAI、Anthropic、DeepSeek、Ollama）
2. ✅ 实现全量LLM参数热配置，零停机更新
3. ✅ 完成RAG评估工作流重塑，支持多维度测试与报告管理
4. ✅ 收拢所有硬编码提示词与魔法值到统一配置层
5. ✅ 提供智能调参建议引擎，自动优化RAG检索效果
6. ✅ 实现LLM调用全链路追踪，支持可观测性与成本分析
7. ✅ 保持100%向下兼容，业务代码无感知升级

---

## 📋 实施原则
1. **兼容性优先**：所有变更保持100%向下兼容，不破坏现有业务逻辑
2. **增量迭代**：按Phase分阶段实施，每个Phase产出可独立运行的功能
3. **测试驱动**：每个功能模块必须包含单元测试与集成测试
4. **文档同步**：所有架构变更同步更新AGENTS.md与相关技术文档
5. **安全可控**：敏感信息（API密钥）严格加密存储，配置变更留审计日志

---

## ✅ 验收标准
### Phase 1 验收
- 可通过配置切换不同LLM提供商，业务功能正常运行
- 修改LLM配置后无需重启服务，15秒内自动生效
- 所有现有LLM调用场景支持多提供商，无功能退化

### Phase 2 验收
- RAG测试集工作流完整：创建→添加案例→运行→生成报告→导出
- 所有硬编码提示词已迁移到PromptManager，无残留魔法值
- 智能调参引擎可根据测试结果生成有效优化建议

### Phase 3 验收
- LLM调用全链路可追踪，展示完整Span层级树与耗时分析
- 成本分析面板可按提供商/模型/场景统计Token消耗与费用
- 所有API新增端点通过安全审计，权限控制正确

---

# 项目概览与文件结构变更

## 📋 文件结构变更总览

### 新增文件

| 文件路径 | 职责 | 所属 Phase |
|---------|------|-----------|
| `src/core/llm/provider_registry.py` | 提供商注册表，(provider, framework) → LLM 类映射 | Phase 1 |
| `src/core/llm/embedding_factory.py` | Embedding 提供商工厂 | Phase 1 |
| `src/core/llm/reranker_factory.py` | Reranker 提供商工厂（预留） | Phase 1 |
| `src/core/llm/config_validator.py` | LLM 参数配置校验层 | Phase 1 |
| `src/core/tracing/context.py` | TraceContext 上下文管理 (contextvars) | Phase 3 |
| `src/core/tracing/span_recorder.py` | Span 记录器，异步写入队列 | Phase 3 |
| `src/core/tracing/sampler.py` | 采样策略实现 | Phase 3 |
| `src/core/tuning/rule_engine.py` | 调参规则引擎 | Phase 2C |
| `src/core/tuning/history_analyzer.py` | 历史对比分析器 | Phase 2C |
| `src/core/tuning/llm_diagnoser.py` | LLM-as-Judge 诊断器 | Phase 2C |
| `src/service/report_exporter.py` | 报告导出服务 (Markdown/PDF) | Phase 2A |
| `src/service/rag_report_service.py` | RAG报告生命周期管理服务 | Phase 2A |
| `src/service/rag_test_case_service.py` | RAG测试用例生成服务（优化版） | Phase 2A |
| `src/core/rag/metrics_calculator.py` | RAG评估指标计算服务 | Phase 2A |
| `src/scripts/sync_rag_test_data_to_mysql.py` | JSON数据同步工具 | Phase 2A |
| `src/config/modules/rag/testing.py` | 测试用例生成配置模块 | Phase 2A |
| `src/repository/trace_repository.py` | Trace 数据访问层 | Phase 3 |
| `src/controller/tuning_controller.py` | 调参建议 API 控制器 | Phase 2C |
| `src/models/trace.py` | Trace 数据模型 | Phase 3 |

### 修改文件

| 文件路径 | 变更内容 | 所属 Phase |
|---------|----------|-----------|
| `src/config/modules/models/llm.py` | 新增 `llm_providers` 全局凭证、`model_pricing` 定价表 | Phase 1 |
| `src/config/modules/models/embedding.py` | 新增 `embedding_provider` 字段 | Phase 1 |
| `src/config/modules/rag/retrieval.py` | 新增 `reranker_provider` 字段（预留） | Phase 1 |
| `src/core/llm/factory.py` | 重构支持多提供商、热更新实例重建 | Phase 1 |
| `src/core/nodes/*.py` | 改造为 provider-agnostic 调用方式 | Phase 1 |
| `src/core/query_router.py` | 改造 LLM 调用方式 | Phase 1 |
| `src/core/metadata_extractor.py` | 改造 LLM 调用方式 | Phase 1 |
| `src/core/layered_content_generator.py` | 改造 LLM 调用方式 | Phase 1 |
| `src/core/memory_manager.py` | 改造 LLM 调用方式 | Phase 1 |
| `src/service/retrieval_service.py` | 改造 LLM 调用方式、统一 DB 路径 | Phase 1/2A |
| `src/service/rag_test_manager.py` | 统一 DB 路径、新增报告管理、扩展指标计算 | Phase 2A |
| `src/core/parsers.py` | 改造 VL 解析为提供商工厂 | Phase 1 |
| `src/core/ml/qwen_scorer.py` | 改造 ML 评分为提供商工厂 | Phase 1 |
| `src/controller/rag_test_controller.py` | 新增统一测试执行API、报告管理接口、优化版草稿生成接口 | Phase 2A |
| `src/models/test_case.py` | 新增RAG评估指标字段、报告导出格式枚举、批次标识字段 | Phase 2A |
| `.ai/full_init_script_mysql57.sql` | 更新3张表DDL（test_case_drafts, test_runs, test_run_results） | Phase 2A |
| `src/controller/monitoring_controller.py` | 新增 Trace 查询 API | Phase 3 |
| `src/core/prompts.py` | 提取硬编码提示词，保留 fallback | Phase 2B |
| `src/config/modules/rules/rules.json` | 新增调参规则、年龄段规则 | Phase 2B/2C |
| `pyproject.toml` | 新增多提供商依赖、weasyprint | Phase 1/2A |

### 前端新增/修改文件

| 文件路径 | 变更内容 | 所属 Phase |
|---------|----------|-----------|
| `src/api/rag-test.ts` | RAG 测试 API 客户端（TypeScript 类型定义+API 封装） | Phase 2A |
| `src/features/rag-eval/components/CasePicker.tsx` | 案例选择器组件 | Phase 2A |
| `src/features/rag-eval/components/TuningSuggestionsPanel.tsx` | 调参建议面板 | Phase 2C |
| `src/features/rag-eval/components/OneClickOptimize.tsx` | 一键优化组件 | Phase 2C |
| `src/features/monitor/components/TraceListView.tsx` | 追踪列表表格 | Phase 3 |
| `src/features/monitor/components/TraceDetailDrawer.tsx` | 追踪详情抽屉 | Phase 3 |
| `src/features/monitor/components/SpanTreeView.tsx` | Span 层级树 | Phase 3 |
| `src/features/monitor/components/SpanDetailPanel.tsx` | Span 详情面板 | Phase 3 |
| `src/features/monitor/components/TraceFilterBar.tsx` | 高级筛选器 | Phase 3 |
| `src/features/monitor/components/CostAnalysisDashboard.tsx` | 成本分析面板 | Phase 3 |
| `src/features/monitor/LLMMonitoringDashboard.tsx` | 新增 Traces 标签页 | Phase 3 |
| `src/features/rag-eval/RagEvaluationPage.tsx` | 修复 TestSetManager 数据流 | Phase 2A |
| `src/pages/SystemConfigPage.tsx` | 重构为容器组件，集成 ExpertMode/WizardMode | Phase 4 |
| `src/pages/SystemConfigPage.module.scss` | 重写样式，支持响应式布局（4 断点） | Phase 4 |
| `src/components/config/ExpertMode.tsx` | 专家模式容器组件 | Phase 4 |
| `src/components/config/WizardMode.tsx` | 向导模式容器组件 | Phase 4 |
| `src/components/config/Sidebar.tsx` | 侧边栏导航组件 | Phase 4 |
| `src/components/config/TopToolbar.tsx` | 顶部工具栏（搜索 + 筛选 + 操作） | Phase 4 |
| `src/components/config/AccordionPanel.tsx` | 手风琴面板组件 | Phase 4 |
| `src/components/config/ConfigCard.tsx` | 配置卡片组件 | Phase 4 |
| `src/components/config/ConfigField.tsx` | 配置字段编辑器（共享） | Phase 4 |
| `src/components/config/ChangeIndicator.tsx` | 修改标记组件 | Phase 4 |
| `src/components/config/HealthScoreCard.tsx` | 健康度卡片组件 | Phase 4 |
| `src/components/config/ModeSwitcher.tsx` | 模式切换组件 | Phase 4 |
| `src/components/config/StepNavigator.tsx` | 步骤导航器组件 | Phase 4 |
| `src/components/config/SearchBox.tsx` | 搜索框组件（支持 ⌘K） | Phase 4 |
| `src/components/config/ImportExportDialog.tsx` | 导入导出对话框 | Phase 4 |
| `src/components/config/constants.ts` | 配置分类常量、场景映射 | Phase 4 |
| `src/store/configStore.ts` | 扩展状态管理（modePreference、healthDiagnostic 等） | Phase 4 |
| `src/features/system-config/` | **删除**（死代码清理） | Phase 4 |

---

## 🏗️ 架构说明

### LLM 多提供商架构

```
┌─────────────────────────────────────────────────────────┐
│                    业务场景层                              │
│  Assessment / Reporting / Validation / Metadata / ...    │
└─────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────┐
│                  LLMServiceFactory                        │
│  ┌─────────────────────────────────────────────────┐    │
│  │  Provider Registry                               │    │
│  │  (dashscope, openai, anthropic, deepseek, ollama)│    │
│  └─────────────────────────────────────────────────┘    │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐     │
│  │ LangChain   │  │ LlamaIndex  │  │ 自定义适配   │     │
│  │ 适配器      │  │ 适配器      │  │             │     │
│  └─────────────┘  └─────────────┘  └─────────────┘     │
└─────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────┐
│                  全局凭证层                                │
│  dashscope: { api_key: "sk-..." }                        │
│  openai: { api_key: "sk-...", base_url: "可选" }         │
│  anthropic: { api_key: "sk-..." }                        │
│  deepseek: { api_key: "sk-..." }                         │
│  ollama: { base_url: "http://localhost:11434" }          │
└─────────────────────────────────────────────────────────┘
```

### 热更新机制

```
配置变更 → ConfigChangedEvent → EventBus
                              ↓
                    ConfigValidator 校验
                              ↓
                    ┌─────────┴─────────┐
                    │ 校验通过           │ 校验失败
                    ↓                   ↓
              实例重建流程          拒绝更新 + 审计日志
                    ↓
          旧实例标记 deprecated
                    ↓
          等待进行中请求完成 (max 30s)
                    ↓
          延迟清理 (15s) / 超时强制清理
                    ↓
          新实例就绪 + 记录日志
```

### 测试集核心工作流

```
创建/选择测试集 (TestSet)
         ↓
添加测试案例 (TestCase) ← 四种途径
  1. 文档导入生成 → LLM 草稿 → 审核 → 归入测试集
  2. 手动创建 → 表单新建 → 归入测试集
  3. 从现有草稿选择 → 勾选审核 → 关联测试集
  4. 从现有案例选择 → 勾选 → 直接关联
         ↓
批量运行测试集 → 生成 TestRun
         ↓
生成评估报告 (Evaluation Report)
         ↓
持久化保存 / 支持删除 / 支持导出
```

### 智能调参三层架构

```
┌─────────────────────────────────────────────────┐
│  Layer 1: 规则引擎 (Rule Engine)                   │
│  根据指标短板快速定位问题方向，给出初步参数建议          │
│  触发条件：任何指标低于阈值                          │
│  输出：2-5 条结构化建议，延迟 <10ms，无成本           │
└──────────────────────┬──────────────────────────┘
                       ▼
┌─────────────────────────────────────────────────┐
│  Layer 2: 历史对比 (History Analysis)              │
│  从历史运行中匹配相似问题，展示"上次改了什么、效果如何"   │
│  触发条件：存在 ≥2 次历史运行记录                     │
│  输出：1-3 条历史参考建议，延迟 <50ms，无成本         │
└──────────────────────┬──────────────────────────┘
                       ▼
┌─────────────────────────────────────────────────┐
│  Layer 3: LLM 诊断 (LLM-as-Judge Diagnosis)       │
│  对 Bad Case 进行语义分析，给出针对性深度建议         │
│  触发条件：Bad Case 数量 ≥ 3 或用户主动触发          │
│  输出：1-2 条深度诊断建议 + 根因分析，延迟 1-3s       │
└─────────────────────────────────────────────────┘
```

### LLM 调用追踪架构

```
┌─────────────────────────────────────────────────┐
│                    Trace                          │
│  trace_id, name, user_id, start_time, end_time   │
│  total_duration_ms, total_tokens, total_cost     │
└──────────────────────┬──────────────────────────┘
                       ▼
┌─────────────────────────────────────────────────┐
│                  Span 层级树                        │
│  ┌─────────────────────────────────────────────┐ │
│  │  Root Span: LangGraph Workflow               │ │
│  │  ├─ NodePre Span                             │ │
│  │  ├─ ValidationNode Span                      │ │
│  │  │   └─ LLM Call Span (qwen-plus)            │ │
│  │  ├─ AssessmentNode Span                      │ │
│  │  │   └─ LLM Call Span (qwen-plus)            │ │
│  │  ├─ RetrievalNode Span                       │ │
│  │  ├─ ScoringNode Span                         │ │
│  │  └─ ReportingNode Span                       │ │
│  │      └─ LLM Call Span (qwen-plus)            │ │
│  └─────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────┘
```

---

## 📦 依赖管理

### Phase 1 新增依赖

```toml
# OpenAI
langchain-openai = "^0.3.0"
llama-index-llms-openai = "^0.3.0"
llama-index-embeddings-openai = "^0.3.0"

# Anthropic
langchain-anthropic = "^0.3.0"
llama-index-llms-anthropic = "^0.4.0"

# Ollama
langchain-ollama = "^0.2.0"
llama-index-llms-ollama = "^0.5.0"
llama-index-embeddings-ollama = "^0.4.0"
```

### Phase 2A 新增依赖

```toml
# PDF 导出
weasyprint = "^62.0"

# 中文分词（草稿去重）
jieba = "^0.42.1"

# Markdown 转 HTML（PDF导出）
markdown = "^3.5.0"
```

---

## 🔧 配置管理

### 全局提供商凭证示例

```json
{
  "llm_providers": {
    "dashscope": { "api_key": "sk-..." },
    "openai": { "api_key": "sk-...", "base_url": "可选的自定义接口地址" },
    "anthropic": { "api_key": "sk-..." },
    "deepseek": { "api_key": "sk-..." },
    "ollama": { "base_url": "http://localhost:11434" }
  }
}
```

### 场景化模型调用配置示例

```json
{
  "provider": "dashscope",
  "model": "qwen-plus",
  "temperature": 0.7,
  "max_tokens": 2000,
  "top_p": 0.8,
  "presence_penalty": 1.0
}
```

---

## 📖 下一步

继续查看各个 Phase 的详细实施方案：

1. [Phase 1: LLM 多提供商 + 热配置](./01-phase-1-llm-providers.md)
2. [Phase 2A: RAG 评估工作流重塑](./02-phase-2a-rag-workflow.md)
3. [Phase 2B: 提示词/配置收拢](./03-phase-2b-prompt-config-cleanup.md)
4. [Phase 2C: 智能调参建议引擎](./04-phase-2c-tuning-engine.md)
5. [Phase 3: LLM 调用追踪](./05-phase-3-llm-tracing.md)
6. [Phase 4: 系统配置页面重构](./06-phase-4-00-overview.md)

---

**返回索引：** [README.md](./README.md)
