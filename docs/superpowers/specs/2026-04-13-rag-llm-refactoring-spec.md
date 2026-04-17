# RAG 评估与 LLM 多模型提供商重构设计规格说明书 (Spec)

## 目录
- [1. 概述](#1-概述)
- [2. RAG 评估工作流重塑](#2-rag-评估工作流重塑)
  - [2.1 以测试集为核心的工作流](#21-以测试集为核心的工作流)
  - [2.2 添加测试案例的四种闭环途径](#22-添加测试案例的四种闭环途径)
  - [2.3 多测试集批量执行与报告生命周期管理](#23-多测试集批量执行与报告生命周期管理)
  - [2.4 前端 UI 修复与增强](#24-前端-ui-修复与增强)
- [3. LLM 多模型提供商扩展](#3-llm-多模型提供商扩展)
  - [3.1 提供商抽象](#31-提供商-provider-抽象)
  - [3.2 支持的模型提供商](#32-支持的模型提供商)
  - [3.3 工厂类重构](#33-工厂类重构)
  - [3.4 Embedding 提供商抽象](#34-embedding-提供商抽象-新增)
  - [3.5 VL 解析与 ML 评分模块抽象](#35-vl-解析与-ml-评分模块抽象-新增)
  - [3.6 依赖包清单](#36-依赖包清单)
  - [3.7 调用点改造清单](#37-调用点改造清单-15-文件)
  - [3.8 Reranker 提供商抽象预留](#38-reranker-提供商抽象预留-新增)
- [4. LLM 参数全量热配置](#4-llm-参数全量热配置)
  - [4.1 全局凭证与场景参数分离设计](#41-全局凭证与场景参数分离设计-参考-opencode-模式)
  - [4.2 零停机热更新机制](#42-零停机热更新机制)
  - [4.3 配置校验层](#43-配置校验层-新增)
  - [4.4 UI 前端适配](#44-ui-前端适配)
- [5. 收拢硬编码提示词与配置](#5-收拢硬编码提示词与配置-system-cleanup)
  - [5.1 提示词全面接入 PromptManager](#51-提示词全面接入-promptmanager-分阶段实施)
  - [5.2 业务配置与魔法值全面接入 ConfigManager](#52-业务配置与魔法值全面接入-configmanager-分阶段实施)
- [6. 简化版 Langfuse LLM 调用追踪](#6-简化版-langfuse-llm-调用追踪-traces)
  - [6.1 现状分析与需求](#61-现状分析与需求)
  - [6.2 数据模型设计](#62-数据模型设计)
  - [6.3 调用链路集成](#63-调用链路集成)
  - [6.4 API 扩展](#64-api-扩展)
  - [6.5 前端追踪视图](#65-前端追踪视图-trace-viewer)
- [7. 风险控制与迁移策略](#7-风险控制与迁移策略)
  - [7.1 回滚策略](#71-回滚策略)
  - [7.2 灰度发布计划](#72-灰度发布计划)
  - [7.3 兼容性保障](#73-兼容性保障)
  - [7.4 安全审计](#74-安全审计-新增)
  - [7.5 文档更新计划](#75-文档更新计划-新增)
- [8. RAG 智能调参建议引擎](#8-rag-智能调参建议引擎)
  - [8.1 需求背景](#81-需求背景)
  - [8.2 方案架构：规则引擎 + 历史对比 + LLM 诊断](#82-方案架构规则引擎--历史对比--llm-诊断)
  - [8.3 规则引擎：指标驱动的参数诊断](#83-规则引擎指标驱动的参数诊断)
  - [8.4 历史对比分析：参数变更效果追踪](#84-历史对比分析参数变更效果追踪)
  - [8.5 LLM-as-Judge 深度诊断：Bad Case 语义分析](#85-llm-as-judge-深度诊断bad-case-语义分析)
  - [8.6 全量参数分组与触发条件](#86-全量参数分组与触发条件)
  - [8.7 API 与前端集成](#87-api-与前端集成)
- [9. 数据库迁移清单](#9-数据库迁移清单-新增)
- [10. 实施待办清单](#10-实施待办清单)
  - [Phase 1: LLM 多提供商 + 热配置](#phase-1-llm-多提供商--热配置)
  - [Phase 2A: RAG 评估工作流重塑](#phase-2a-rag-评估工作流重塑)
  - [Phase 2B: 提示词/配置收拢](#phase-2b-提示词配置收拢)
  - [Phase 2C: 智能调参建议引擎](#phase-2c-智能调参建议引擎)
  - [Phase 3: LLM 调用追踪](#phase-3-llm-调用追踪)

## 1. 概述

本文档详细规定了六个主要系统升级的需求与设计方案。整体实施分为四个阶段（Phase 2 拆分为 2A/2B/2C 以降低单次变更风险）：

- **Phase 1**: LLM 多提供商 + 热配置（基础设施，影响面广但逻辑清晰）
- **Phase 2A**: RAG 评估工作流重塑（业务功能，前后端协同，独立可验证）
- **Phase 2B**: 提示词/配置收拢（系统清理，按 P0/P1/P2 分批迁移）
- **Phase 2C**: 智能调参建议引擎（依赖 Phase 2A 的测试报告数据，MVP 先上线规则引擎层）
- **Phase 3**: LLM 调用追踪（可观测性，可独立迭代）

### 六大升级目标
1. 重塑 RAG 评估工作流，使其严格以"测试集 (TestSet)"为核心。
2. 扩展 LLM 服务，支持除 DashScope 之外的多个模型提供商 (Provider)，并解耦全局凭证与场景参数。
3. 实现所有 LLM 参数的全量热更新 (Hot-Reload) 能力。
4. 全面清查并收拢散落在代码中的硬编码提示词 (Prompts) 与业务配置 (Configs)，统一接入管理系统。
5. 引入类似 Langfuse 的简化版 LLM 调用追踪 (Traces) 系统，全记录模型的输入、输出及实时调用参数。
6. 构建 RAG 智能调参建议引擎，基于测试结果自动诊断问题并给出可操作的参数优化建议。

## 2. RAG 评估工作流重塑

### 2.1 以测试集为核心的工作流
整个测试流程必须遵循严格的自顶向下层级结构：
`创建/选择测试集 -> 往测试集中添加测试案例 -> 批量运行测试集`

### 2.2 添加测试案例的四种闭环途径
测试案例只能通过以下方式添加到测试集中：
1. **文档导入生成**：上传 PDF/EPUB -> LLM 自动生成草稿 -> 人工审核 -> 审核通过的案例自动归入当前测试集。
2. **手动创建**：在测试集详情页通过表单新建单个测试案例，并归入当前集合。
3. **从现有草稿中选择**：从其他文档解析任务遗留的草稿库中勾选，审核后关联到当前测试集。
4. **从现有案例中选择**：从系统已有的正式测试案例库中勾选，直接关联到当前测试集。

#### 2.2.1 测试用例草稿生成优化
针对当前文档导入生成测试用例草稿数量少、速度慢的问题，新增以下优化规范：
##### 生成能力提升
- **数量要求**：单篇文档默认生成不少于100条草稿，可根据文档长度动态调整：
  - 短文档（<50页）：最小生成20条
  - 中等长度文档（50-200页）：生成100条
  - 长文档（>200页）：最大生成200条
- **多维度差异化**：生成的草稿需覆盖以下互不重叠的维度，确保多样性：
  | 维度类型 | 可选值 | 覆盖要求 |
  |----------|--------|----------|
  | 发展领域 | 粗大动作、精细动作、语言发展、认知能力、社交情感、感觉统合 | 覆盖文档涉及的所有领域 |
  | 年龄段 | 0-1岁、1-3岁、3-6岁、6-12岁 | 每个年龄段至少生成10条草稿（文档未覆盖的年龄段除外） |
  | 查询类型 | 事实性查询（是什么/有什么）、比较性查询（区别/对比）、方案性查询（怎么做/如何）、原因分析性查询（为什么/原因） | 每种查询类型至少生成15条草稿 |
  | 难度级别 | 入门级（基础概念）、中级（应用场景）、高级（复杂问题） | 每个难度级别至少生成20条草稿 |

##### 性能优化方案
- **批量并行生成**：按章节对文档进行分块处理，每个章节独立并行生成草稿，并发数默认20（复用现有元数据提取的并发配置）
- **提示词优化**：优化`test_case_draft_generation`提示词，要求单次LLM调用生成10-15条草稿，大幅减少调用次数
- **缓存复用**：复用文档解析、分块、元数据提取的已有结果，避免重复处理
- **增量生成**：支持断点续传，已生成的草稿不会重复生成，中断后可从断点继续

##### 质量控制规则
- **去重校验**：生成时自动校验草稿相似度，相似度超过0.8的自动丢弃，确保内容唯一性
- **完整性校验**：每条草稿必须包含query、age、domain、expected_keywords四个必填字段，缺失的自动补全或丢弃
- **相关性校验**：草稿查询内容必须与对应章节内容相关，相关性低于0.6的自动丢弃

##### 新增配置项
在`src/config/modules/rag/testing.py`中新增以下可配置参数：
| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `test_case_draft_default_count` | Integer | 100 | 单篇文档默认生成草稿数量 |
| `test_case_draft_max_count` | Integer | 200 | 单篇文档最大生成草稿数量 |
| `test_case_draft_min_count` | Integer | 20 | 单篇文档最小生成草稿数量 |
| `test_case_draft_concurrency` | Integer | 20 | 草稿生成并发数 |
| `test_case_draft_deduplication_threshold` | Float | 0.8 | 草稿去重相似度阈值 |

### 2.3 多测试集批量执行与报告生命周期管理
- **测试批次 (Test Run)**：一个测试集（或由用户临时勾选的一批测试案例/多个测试集）在单次运行后，将生成一个唯一的"测试批次记录 (TestRun)"。
- **统一执行路径**：
  - **废除 JSON 文件路径**：当前 `list_test_runs` 和 `get_test_run` 方法仍读取 JSON 文件，必须统一改为读取 MySQL 数据库。
  - **完整指标计算**：`TestRunResult` 模型需补充 `mrr` (Mean Reciprocal Rank) 和 `ndcg` (NDCG@K) 字段，确保 DB 路径与原有文件路径的指标一致性。
  - **执行入口统一**：所有测试执行必须通过 `POST /rag/test/run` 接口，使用 `RetrievalService.search()` 进行实际 RAG 检索。
- **报告生成**：该批次执行完毕后，系统会严格基于该次运行的案例范围生成一份静态的**评估测试报告 (Evaluation Report)**。报告展示该批次的整体指标（如综合准确率、召回率、MRR、NDCG、耗时等），并支持按特定测试集或特定领域 (Domain) 进行下钻数据分析。
- **报告可追溯与可删除**：
  - 每次运行生成的报告都会被持久化保存，用户可以在"历史报告列表"中查看过往任何一次运行的测试结果。
- **支持删除**：用户可以手动删除不再需要的历史测试报告及其关联的运行明细数据，以释放存储空间并保持列表整洁。删除操作前端需增加二次确认提示。
- **级联删除策略**：删除 `TestRun` 时，直接物理删除记录，级联删除其关联的所有 `TestRunResult` 明细数据和对应的报告文件，无软删除/保留期，删除后数据不可恢复。
- **报告导出**：支持将评估报告导出为 Markdown 或 PDF 格式，便于离线查看和分享。
  - **PDF 导出依赖**：引入 `weasyprint` 库（基于 CSS 排版，支持中文），需在系统层面安装 Pango 和 Cairo 依赖。备选方案：`pdfkit`（依赖 wkhtmltopdf）。

### 2.4 前端 UI 修复与增强
- **修复 TestSetManager 数据流**：当前 `RagEvaluationPage.tsx` 中 `<TestSetManager testSets={[]} ... />` 传入空数组，必须接通 `getTestSets` API 调用。
- **案例选择器组件 (Case Picker)**：实现可复用的案例选择器 UI，支持：
  - 从正式测试案例库中勾选并关联到当前测试集
  - 从草稿库中勾选审核后关联到当前测试集
  - 批量操作（全选/反选/按领域筛选/按年龄筛选）
  - 反向查询：查看某个测试案例属于哪些测试集
- **测试集详情页增强**：展示已关联的案例列表，支持移除案例操作。

## 3. LLM 多模型提供商扩展

### 3.1 提供商 (Provider) 抽象
在系统配置中引入 `provider` 字段，以解除 `LLMServiceFactory` 对 DashScope 实现的硬编码绑定。

### 3.2 支持的模型提供商
- **前提要求**：所支持的模型提供商必须**同时兼容 LangChain 和 LlamaIndex** 两个框架。
- **提供商列表**：
  - `dashscope` (通义千问系列 - 保持现有兼容性)
  - `openai` (GPT 系列)
  - `anthropic` (Claude 系列)
  - `deepseek` (通过 OpenAI 兼容接口或官方 SDK 接入)
  - `ollama` (支持本地部署的开源模型)

### 3.3 工厂类重构
重构 `LLMServiceFactory`，使其能够根据传入的 `provider` 值，动态加载对应的 LangChain/LlamaIndex 官方或自定义适配器类。

**提供商注册表 (Provider Registry)**：
- 创建 `(provider, framework)` 到 LLM 类构造函数的映射表：
  | Provider | LangChain 类 | LlamaIndex 类 |
  |----------|-------------|---------------|
  | dashscope | `ChatTongyi` | `DashScope` |
  | openai | `ChatOpenAI` | `OpenAI` |
  | anthropic | `ChatAnthropic` | `Anthropic` |
  | deepseek | `ChatOpenAI` (base_url 覆盖) | `OpenAI` (base_url 覆盖) |
  | ollama | `ChatOllama` | `Ollama` |
- 凭证自动注入：根据 `provider` 字段从全局配置中提取对应的 `api_key` 或 `base_url` 注入到模型客户端。

### 3.4 Embedding 提供商抽象 (新增)
当前 `SafeDashScopeEmbedding` 和 LlamaIndex embedding 同样硬编码 DashScope，需同步抽象：
- **配置扩展**：`src/config/modules/models/embedding.py` 增加 `embedding_provider` 字段
- **工厂模式**：创建 `EmbeddingFactory`，支持 `dashscope`、`openai`、`ollama` 等提供商
- **影响范围**：
  - `src/core/embedding.py`：创建 provider-agnostic 的 embedding 包装类
  - `src/config/__init__.py`：移除直接引用 `SafeDashScopeEmbedding` 的代码

### 3.5 VL 解析与 ML 评分模块抽象 (新增)
以下模块直接调用 DashScope SDK/HTTP API，需纳入提供商抽象：
- **VL 解析** (`src/core/parsers.py`)：当前使用 `dashscope.MultiModalConversation.call()`，需改为通过提供商工厂获取 VL 模型实例
- **ML 评分** (`src/core/ml/qwen_scorer.py`)：当前直接调用 DashScope HTTP API，需改为通过提供商工厂获取评分模型实例

### 3.8 Reranker 提供商抽象预留 (新增)
当前 Cross-Encoder 使用本地模型 `BAAI/bge-reranker-v2-m3`，暂不纳入提供商抽象，但需预留扩展点：
- 在 `src/config/modules/rag/retrieval.py` 中增加 `reranker_provider` 字段（默认 `local`）
- 创建 `RerankerFactory` 接口，支持 `local`（本地模型）和 `cloud`（如 Cohere API）两种模式
- MVP 阶段仅实现 `local` 模式，云端模式作为后续扩展

### 3.6 依赖包清单
在 `pyproject.toml` 中新增以下依赖（版本号锁定到当前最新稳定版）：
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

# PDF 导出 (Phase 2A)
weasyprint = "^62.0"
```

**凭证 Schema 说明**：
- `dashscope`/`openai`/`anthropic`/`deepseek`：`api_key` 为必填，`base_url` 为可选（用于自定义代理/镜像）
- `ollama`：`api_key` 为可选（通常为空），`base_url` 为必填（默认 `http://localhost:11434`）

### 3.7 调用点改造清单 (15+ 文件)
以下文件中的 `settings.dashscope_api_key` 检查和 `LLMServiceFactory.create()` 调用需更新为 provider-agnostic 方式：
- `src/core/nodes/assessment.py`
- `src/core/nodes/validation.py`
- `src/core/nodes/reporting.py`
- `src/core/nodes/scoring.py`
- `src/core/nodes/preprocessing.py`
- `src/core/nodes/retrieval.py`
- `src/core/query_router.py`
- `src/core/metadata_extractor.py`
- `src/core/layered_content_generator.py`
- `src/core/memory_manager.py`
- `src/service/retrieval_service.py`
- `src/service/rag_test_manager.py`
- `src/controller/task_controller.py`
- `src/core/parsers.py`
- `src/core/ml/qwen_scorer.py`

## 4. LLM 参数全量热配置

### 4.1 全局凭证与场景参数分离设计 (参考 OpenCode 模式)
为了简化用户配置，避免在每个场景中重复输入 API Key，采用**全局提供商凭证**与**具体场景参数**解耦的设计：

**1. 全局提供商配置 (Global Provider Credentials)**
用户在系统全局首先配置好各厂家的 API Key 或本地服务的请求地址（如 Ollama）：
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

**2. 场景化模型调用配置 (Scenario-specific Model Config)**
在配置具体的 9 大业务场景（如 `model_report_generation`）时，用户**无需再次输入 API Key**。只需选择 `provider` 并手动输入 `model` 名称，即可对该调用的专属参数进行控制：
```json
{
  "provider": "dashscope",
  "model": "qwen3.5-plus",
  "temperature": 0.7,
  "max_tokens": 2000,
  "top_p": 0.8,
  "presence_penalty": 1.0
}
```
*注：系统在实例化具体场景的模型时，会自动根据 `provider` 字段从全局配置中提取对应的凭证（API Key 或 base_url）注入到模型客户端中。项目实际使用 `qwen3.5-plus` / `qwen3.5-turbo` / `qwen3-omni-flash` 模型系列。*

### 4.2 零停机热更新机制
- 将所有 LLM 相关的配置项从冷更新名单 (`_is_hot_reloadable = False`) 中移除，并接入现有的配置热更新机制。
- **动态实例重建**：监听 `EventBus` 上的 `ConfigChangedEvent` 事件。当特定业务场景的 LLM 参数发生变更时，工厂类将优雅地销毁旧实例，并在下次调用时使用新参数无缝重建实例。
- **实例清理策略（引用计数机制）**：
  - **引用计数追踪**：每个缓存实例维护活跃请求计数 (`_active_requests`)，`create()` 时 +1，`release()` 时 -1
  - **代际版本控制**：配置变更时增加 `_current_generation` 代际计数，旧实例标记为旧代际并移入 `_deprecated_instances`
  - **延迟清理触发**：`release()` 时检查引用计数，归零时自动触发 `_try_cleanup_deprecated()` 清理废弃实例
  - **优雅关闭**：`shutdown()` 方法等待所有活跃请求完成（最多等待 30 秒），超时后强制清理
  - **资源释放**：清理时调用实例的 `dispose()` 方法（若支持），确保 GPU 内存等资源正确释放
  - **清理日志**：记录实例销毁事件，包括场景名称、旧模型名称、代际版本、引用计数
  - **锁超时保护**：使用 `asyncio.wait_for(lock.acquire(), timeout=10.0)` 防止死锁

### 4.3 配置校验层 (新增)
热更新前必须对新参数做合法性校验，避免无效配置导致实例重建失败或运行时异常：

**校验规则**：
| 参数 | 校验规则 | 错误处理 |
|------|---------|---------|
| `temperature` | `0 <= value <= 2.0` | 拒绝更新，返回错误提示 |
| `max_tokens` | `1 <= value <= 32000` | 拒绝更新，返回错误提示 |
| `top_p` | `0.01 <= value <= 1.0` | 拒绝更新，返回错误提示 |
| `presence_penalty` | `-2.0 <= value <= 2.0` | 拒绝更新，返回错误提示 |
| `frequency_penalty` | `-2.0 <= value <= 2.0` | 拒绝更新，返回错误提示 |
| `provider` | 必须在 Provider Registry 中 | 拒绝更新，返回错误提示 |
| `model` | 非空字符串 | 拒绝更新，返回错误提示 |

**校验流程**：
1. 接收配置变更事件
2. 执行参数校验 → 若失败，记录审计日志并拒绝应用
3. 校验通过后，触发实例重建流程
4. 若实例重建失败，回滚到旧配置并告警

### 4.4 UI 前端适配
升级系统配置页 (`/system-config`) 的前端表单，支持上述结构化 JSON 对象的展示与动态修改。

## 5. 收拢硬编码提示词与配置 (System Cleanup)

### 5.1 提示词全面接入 PromptManager (分阶段实施)
目前系统中存在大量直接硬编码在代码中的系统提示词 (System Messages) 和 PromptTemplate。必须将以下内容全部提取并迁移至 MySQL 数据库，通过 `PromptManager` 统一进行版本控制与 A/B 测试分发。

**实施优先级**：

**P0 - 节点级系统提示词 (核心评估流程)**：
| Prompt Key | 来源文件 | 说明 |
|------------|----------|------|
| `assessment_system` | `src/core/nodes/assessment.py:67` | 儿童发展评估专家系统消息 |
| `reporting_system` | `src/core/prompts.py:182-297` + `src/core/nodes/reporting.py:226` | 报告生成专家系统消息 |
| `validation_system` | `src/core/prompts.py:102-106` | 数据校验系统消息 |
| `intensity_inference` | `src/core/prompts.py:108-120` | 活动强度推断 |
| `category_inference` | `src/core/prompts.py:122-138` | 活动类别推断 |

**P1 - RAG 检索相关提示词**：
| Prompt Key | 来源文件 | 说明 |
|------------|----------|------|
| `rag_query_template` | `src/core/prompts.py:6` | 检索节点查询模板 |
| `query_rewrite` | `src/core/prompts.py:8-19` + `src/service/retrieval_service.py:830-832` | 查询重写 |
| `synonym_expansion` | `src/core/prompts.py:21-46` + `src/service/retrieval_service.py:949-951` | 同义词扩展 |
| `query_classification` | `src/core/query_router.py:174-194` + `208-209` | 查询分类 |

**P2 - 元数据与内容生成提示词**：
| Prompt Key | 来源文件 | 说明 |
|------------|----------|------|
| `metadata_extraction` | `src/core/prompts.py:52-73` + `src/core/metadata_extractor.py:187` | 元数据提取 |
| `test_case_draft_generation` | `src/core/prompts.py:75-95` | 测试用例草稿生成 |
| `layered_content_l0` | `src/core/layered_content_generator.py:155-159` | L0 摘要生成 |
| `layered_content_l1` | `src/core/layered_content_generator.py:187-191` | L1 概览生成 |
| `layered_content_batch` | `src/core/layered_content_generator.py:267-274` | 批量摘要生成 |
| `layered_content_combined` | `src/core/layered_content_generator.py:355-361` | L0+L1 联合生成 |

**操作要求**：
- 代码中仅保留 `prompt_manager.get_prompt("key_name")` 的调用
- 确保相关的占位符（Variables）在模板中正确对应
- 每个提示词需设置合理的 fallback 值，确保 PromptManager 不可用时系统可降级运行

### 5.2 业务配置与魔法值全面接入 ConfigManager (分阶段实施)
清除散落在核心算法与业务流中的魔法值 (Magic Numbers) 和硬编码规则，将其提升至 `ConfigManager` 的相应模块。

**实施优先级**：

**P0 - LLM 参数集中化** (涉及 15+ 文件，60+ 处)：
| 场景 | 当前配置方式 | 目标配置项 |
|------|-------------|-----------|
| assessment | `temperature=0.5`, `max_tokens=1024` | `llm.assessment.temperature`, `llm.assessment.max_tokens` |
| reporting | `temperature=0.7`, `max_tokens=8000` | `llm.reporting.temperature`, `llm.reporting.max_tokens` |
| validation | `temperature=0.3`, `max_tokens=512` | `llm.validation.temperature`, `llm.validation.max_tokens` |
| metadata_extraction | `temperature=0.4`, `max_tokens=1024` | `llm.metadata_extraction.temperature`, `llm.metadata_extraction.max_tokens` |
| query_rewrite | `temperature=0.6`, `max_tokens=256` | `llm.query_rewrite.temperature`, `llm.query_rewrite.max_tokens` |
| synonym_expansion | `temperature=0.8`, `max_tokens=256` | `llm.synonym_expansion.temperature`, `llm.synonym_expansion.max_tokens` |
| query_classification | `temperature=0.2`, `max_tokens=128` | `llm.query_classification.temperature`, `llm.query_classification.max_tokens` |
| layered_content | `temperature=0.4`, `max_tokens=256/1024/4096` | `llm.layered_content.temperature`, `llm.layered_content.max_tokens_l0/l1/batch` |

**P1 - RAG 检索阈值与参数**：
| 配置项 | 当前值 | 来源文件 | 目标配置键 |
|--------|--------|----------|-----------|
| 去重包含阈值 | `>0.8` | `retrieval_service.py:566` | `rag.dedup.containment_threshold` |
| 长度差异阈值 | `<0.2` | `retrieval_service.py:574` | `rag.dedup.length_diff_threshold` |
| difflib 相似度阈值 | `>0.9` | `retrieval_service.py:581` | `rag.dedup.similarity_threshold` |
| 显示分数基准 | `0.60` | `retrieval_service.py:725` | `rag.scoring.base_display_score` |
| 显示分数上限 | `0.98` | `retrieval_service.py:725` | `rag.scoring.max_display_score` |
| 关键词匹配加成 | `*0.2` | `retrieval_service.py:713` | `rag.scoring.keyword_bonus_multiplier` |
| 年龄适配权重 | `0.7/0.3` | `retrieval_service.py:504` | `rag.scoring.age_fit_weights` |
| 高相关性阈值 | `>0.8` | `scoring.py:278` | `rag.scoring.high_relevance_threshold` |

**P2 - 文档处理与业务规则**：
| 配置项 | 当前值 | 来源文件 | 目标配置键 |
|--------|--------|----------|-----------|
| 元数据缓存大小 | `10000` | `metadata_extractor.py:120` | `rag.metadata.cache_max_size` |
| 最小文本长度 | `10` | `metadata_extractor.py:148` | `rag.metadata.min_text_length` |
| 文本截断长度 | `2000` | `metadata_extractor.py:157` | `rag.metadata.text_truncation_length` |
| 最大主题数 | `8` | `metadata_extractor.py:224` | `rag.metadata.max_topics` |
| 英文检测阈值 | `>0.7` | `metadata_processor.py` | `rag.chunking.english_threshold` |
| 分块合并倍率 | `1.2/1.5` | `metadata_processor.py` | `rag.chunking.merge_ratio` |
| 并行线程数 | `20` | `metadata_processor.py` | `rag.metadata.max_workers` |

**业务规则分离策略**：
- `age_filter.py` 中的年龄段划分参数 (tolerance/strictness/weight) 提取到 `rules.json`
- `child_development_engine.py` 中的年龄边界和推荐规则提取到 `rules.json`
- **保留核心算法在代码中**：仅将可配置参数外部化，避免逻辑碎片化
- 年龄段划分规则示例 (`rules.json` 中的 `age_filter_stages`)：
```json
{
  "age_filter_stages": {
    "infant": { "age_max": 1, "tolerance": 1, "strictness": 0.9, "weight": 0.5 },
    "toddler": { "age_max": 3, "tolerance": 2, "strictness": 0.8, "weight": 0.4 },
    "preschool": { "age_max": 6, "tolerance": 2, "strictness": 0.7, "weight": 0.3 },
    "school_age": { "age_max": 12, "tolerance": 3, "strictness": 0.6, "weight": 0.25 }
  }
}
```

## 6. 简化版 Langfuse LLM 调用追踪 (Traces)

### 6.1 现状分析与需求
目前的 LLM 监控仅提供了聚合的统计数据（如总调用次数、Token 消耗、平均延迟和模型分布饼图），以及简单的 `LLMCallLog` 记录。但 `LLMCallLog` 缺乏对实际**输入内容 (Prompt)**、**输出结果 (Completion)** 和 **当前调用参数 (如 Temperature, Provider 等)** 的记录，无法用于故障排查 (Debug) 或效果分析。
为了满足深度分析的需求，引入类似 Langfuse 的调用追踪功能（简化版）。

### 6.2 数据模型设计

**新增 Trace 模型** (`traces` 表)：
用于表示一次完整的工作流执行（如一次评估请求、一次测试运行），与 `LLMCallLog` 建立一对多关系。

| 字段 | 类型 | 说明 |
|------|------|------|
| `trace_id` | String(64) PK | 唯一追踪 ID (UUID) |
| `name` | String(255) | 追踪名称 (如 "assessment_run", "test_batch_execution") |
| `user_id` | String(64) | 发起用户 ID (可选) |
| `session_id` | String(64) | 会话 ID (可选) |
| `metadata` | JSON | 附加上下文 (如 child_profile_id, test_run_id) |
| `start_time` | DateTime | 追踪开始时间 |
| `end_time` | DateTime | 追踪结束时间 |
| `total_duration_ms` | Integer | 总耗时 |
| `total_tokens` | Integer | 总 Token 消耗 |
| `total_cost` | DECIMAL(10,4) | 总成本 (估算) |
| `status` | Enum | success/failed/partial |
| `created_at` | DateTime | 创建时间 |

**扩展 LLMCallLog 模型** (`llm_call_logs` 表)：
将单次 LLM 调用作为 Trace 中的 Span，增加以下关键字段：

| 字段 | 类型 | 说明 |
|------|------|------|
| `trace_id` | String(64) | 关联的追踪 ID (外键 -> traces.trace_id) |
| `span_id` | String(64) | 当前 Span 唯一 ID (UUID) |
| `parent_span_id` | String(64) | 父 Span ID (用于构建层级树) |
| `prompt_messages` | JSON/TEXT | 完整输入消息数组 (system/user/assistant 角色) |
| `completion_message` | TEXT | 完整输出内容 |
| `call_parameters` | JSON | 实际调用参数 (provider, temperature, max_tokens, top_p 等) |
| `model_parameters` | JSON | 模型专属参数 |
| `user_id` | String(64) | 发起用户 ID |
| `session_id` | String(64) | 会话 ID |
| `cost` | DECIMAL(10,4) | 单次调用成本 (估算) |
| `tags` | JSON | 分类标签 (如 ["assessment", "qwen-plus"]) |
| `completion_start_time_ms` | Integer | 首 Token 延迟 (Time to First Token) |
| `level` | Enum | INFO/WARNING/ERROR |

**性能优化策略**：
- **截断存储**：`prompt_messages` 和 `completion_message` 默认截断至前 8000 字符（可配置 `trace_truncate_length`），完整内容存储于可选的 `full_prompt_path` / `full_completion_path`（本地文件或对象存储）
- **异步写入**：使用独立队列异步写入追踪数据，不阻塞主流程
- **采样策略**：支持采样率配置，降低数据库写入压力
  - `trace_sample_rate`：默认 `1.0`（全量），可设为 `0.1`（10% 随机采样）
  - `trace_error_sample_rate`：默认 `1.0`（错误全量保留），确保所有失败调用都被记录
  - 采样逻辑：`random() < sample_rate or is_error` → 写入
- **TTL 清理**：支持按时间自动清理过期追踪数据（默认保留 30 天）
- **索引优化**：`trace_id`, `span_id`, `user_id`, `created_at` 建立索引

**成本计算模型**：
- 在 `src/config/modules/models/llm.py` 中新增 `model_pricing` 配置，存储各模型单价：
```json
{
  "model_pricing": {
    "qwen-plus": { "input_per_million": 0.004, "output_per_million": 0.012, "currency": "CNY" },
    "gpt-4o": { "input_per_million": 2.50, "output_per_million": 10.00, "currency": "USD" },
    "claude-sonnet-4-20250514": { "input_per_million": 3.00, "output_per_million": 15.00, "currency": "USD" }
  }
}
```
- 成本计算公式：`cost = (input_tokens / 1_000_000) * input_price + (output_tokens / 1_000_000) * output_price`
- 若模型未在定价表中，`cost` 字段为 `NULL`，前端展示为 "未配置"

### 6.3 调用链路集成
- **LangGraph 集成**：在 LangGraph 工作流的每个节点执行前后自动创建 Span
  - NodePre -> ValidationNode -> AssessmentNode -> RetrievalNode -> ScoringNode -> ReportingNode
  - 每个 Span 记录节点名称、输入状态、输出状态、耗时
- **测试执行集成**：在 `RagTestManager.execute_batch` 中为每个测试用例创建独立 Trace
- **上下文传递机制**（使用 `contextvars`）：

**TraceContext 实现方案**：
```python
# src/core/tracing/context.py
from contextvars import ContextVar

trace_id: ContextVar[str | None] = ContextVar("trace_id", default=None)
span_stack: ContextVar[list[str]] = ContextVar("span_stack", default_factory=list)

@contextmanager
async def trace_context(name: str, metadata: dict | None = None):
    """创建 Trace 上下文，适用于 async 环境"""
    tid = str(uuid4())
    token = trace_id.set(tid)
    span_stack.set([])
    try:
        yield tid
    finally:
        trace_id.reset(token)

@contextmanager
def create_span(name: str) -> Generator[str, None, None]:
    """创建 Span 并维护父子关系栈"""
    parent_id = span_stack.get()[-1] if span_stack.get() else None
    span_id = str(uuid4())
    stack = span_stack.get().copy()
    stack.append(span_id)
    token = span_stack.set(stack)
    try:
        yield span_id
    finally:
        span_stack.set(span_stack.get()[:-1])
        span_stack.reset(token)
```

**在 LangGraph 中的集成方式**：
```python
# 在 LangGraph 的 StateGraph 中使用 middleware 模式
class TracingMiddleware:
    async def __call__(self, request, call_next):
        async with trace_context("assessment_run") as tid:
            with create_span("NodePre") as span_id:
                # 执行节点逻辑
                result = await call_next(request)
                # 记录 Span 输出
            return result
```

**并发安全说明**：
- `contextvars` 在 `asyncio` 中是 task-local 的，每个异步任务有独立的上下文副本
- 使用 `asyncio.create_task()` 创建新任务时，子任务会**继承**父任务的上下文快照，但后续修改互不影响
- 在 `asyncio.gather()` 并发场景中，每个并发分支拥有独立的 `trace_id` 和 `span_stack`，不会互相污染
- 若需要在并发分支间共享同一 Trace 但不同 Span，应在 `create_task` 前显式设置 `trace_id.set(parent_trace_id)`

### 6.4 API 扩展

**后端 API 新增接口**：

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/v1/monitoring/traces` | GET | 分页查询追踪列表，支持按场景、模型、状态、用户、时间范围筛选 |
| `/api/v1/monitoring/traces/{trace_id}` | GET | 获取单次追踪的完整数据，包含所有 Span 层级树 |
| `/api/v1/monitoring/traces/{trace_id}/spans/{span_id}` | GET | 获取单个 Span 的详细信息 |
| `/api/v1/monitoring/logs` | GET | 查询原始 LLM 调用日志，支持高级筛选 |
| `/api/v1/monitoring/logs/{request_id}` | GET | 获取单次调用的详细数据 |
| `/api/v1/monitoring/cost` | GET | 成本分析接口，按场景/模型/时间段统计 |
| `/api/v1/monitoring/latency` | GET | 延迟分布接口，返回 P50/P95/P99 延迟 |
| `/api/v1/monitoring/errors` | GET | 错误分析接口，错误分类和趋势 |

### 6.5 前端追踪视图 (Trace Viewer)

**前端页面升级 (`LLMMonitoringDashboard.tsx`)**：
- 增加一个全新的 **"调用追踪 (Traces)"** 标签页

**列表视图**：
| 列 | 说明 |
|----|------|
| 时间 | 调用时间 (支持排序) |
| 场景/名称 | Trace 名称或场景名 |
| 模型 | 使用的模型名称 |
| 状态 | 成功/失败/部分成功 (带颜色标识) |
| Token | 总 Token 消耗 |
| 延迟 | 总耗时 (ms) |
| 成本 | 估算成本 |
| 操作 | 查看详情/复制 Trace ID |

**详情视图 (Drawer/弹窗)**：
- **Span 层级树**：以树形结构展示 Trace 下的所有 Span，支持展开/折叠
  - 根节点: Trace 基本信息 (名称、用户、时间范围、总成本)
  - 子节点: 各 LangGraph 节点的 Span
  - 叶子节点: 具体 LLM 调用的 Span
- **Span 详情面板** (点击 Span 后展示)：
  - 基本信息：Span ID、父 Span ID、耗时、Token、状态
  - 输入 (Prompt)：完整消息数组，支持 Markdown 渲染，可复制
  - 输出 (Completion)：模型返回内容，支持 Markdown 渲染，可复制
  - 调用参数：provider、model、temperature、max_tokens 等超参数列表
  - 错误信息 (如有)：错误类型、堆栈跟踪
- **高级筛选器**：
  - 时间范围选择器
  - 场景/模型多选下拉框
  - 状态筛选 (成功/失败/全部)
  - 用户 ID 搜索
  - Trace ID 精确搜索
  - 标签筛选

**新增前端组件**：
| 组件 | 说明 |
|------|------|
| `TraceListView.tsx` | 追踪列表表格 |
| `TraceDetailDrawer.tsx` | 追踪详情抽屉 |
| `SpanTreeView.tsx` | Span 层级树组件 |
| `SpanDetailPanel.tsx` | Span 详情面板 |
| `TraceFilterBar.tsx` | 高级筛选器 |
| `CostAnalysisDashboard.tsx` | 成本分析面板 |
| `LatencyChart.tsx` | 延迟分布图表 |

## 8. RAG 智能调参建议引擎

### 8.1 需求背景
当前 RAG 系统拥有 70+ 可调参数，分布在检索、分块、流水线、缓存等模块。当测试指标不达标时（如 Recall < 0.7），用户面临以下痛点：
- **参数过多无从下手**：不清楚哪个参数对当前问题影响最大
- **缺乏因果关系**：不知道改某个参数会带来什么副作用
- **无法复用经验**：历史调参经验没有沉淀，每次都要重新摸索

**目标**：基于测试结果自动诊断问题根因，给出可操作、可解释、可验证的参数优化建议，形成"测试 → 诊断 → 调参 → 复测"的闭环。

### 8.2 方案架构：规则引擎 + 历史对比 + LLM 诊断

采用三层递进式架构，兼顾实现成本、效果和可解释性：

```
┌─────────────────────────────────────────────────┐
│                  用户查看测试报告                    │
└──────────────────────┬──────────────────────────┘
                       ▼
┌─────────────────────────────────────────────────┐
│  Layer 1: 规则引擎 (Rule Engine)                   │
│  根据指标短板快速定位问题方向，给出初步参数建议          │
│  触发条件：任何指标低于阈值                          │
│  输出：2-5 条结构化建议                              │
└──────────────────────┬──────────────────────────┘
                       ▼
┌─────────────────────────────────────────────────┐
│  Layer 2: 历史对比 (History Analysis)              │
│  从历史运行中匹配相似问题，展示"上次改了什么、效果如何"   │
│  触发条件：存在 ≥2 次历史运行记录                     │
│  输出：1-3 条历史参考建议                            │
└──────────────────────┬──────────────────────────┘
                       ▼
┌─────────────────────────────────────────────────┐
│  Layer 3: LLM 诊断 (LLM-as-Judge Diagnosis)       │
│  对 Bad Case 进行语义分析，给出针对性深度建议         │
│  触发条件：Bad Case 数量 ≥ 3 或用户主动触发          │
│  输出：1-2 条深度诊断建议 + 根因分析                  │
└─────────────────────────────────────────────────┘
```

**各层职责边界**：
| 层级 | 输入 | 输出 | 延迟 | 成本 |
|------|------|------|------|------|
| 规则引擎 | 聚合指标 (precision/recall/f1/mrr/ndcg) | 参数调整建议 (参数名、当前值、建议值、预期效果) | <10ms | 无 |
| 历史对比 | 历史 TestRun 数据 + 配置版本快照 | 历史调参记录 (时间、变更、指标变化) | <50ms | 无 |
| LLM 诊断 | Bad Case 列表 + 查询内容 + 检索结果 | 自然语言诊断 + 根因分析 + 行动建议 | 1-3s | LLM 调用 |

### 8.3 规则引擎：指标驱动的参数诊断

**核心逻辑**：根据指标短板映射到参数调整建议。

#### 8.3.1 指标-参数映射规则

| 问题类型 | 触发条件 | 建议方向 | 相关参数 | 建议动作 |
|---------|---------|---------|---------|---------|
| **召回不足** | Recall < 0.7 | 扩大检索范围 | `rag_hybrid_bm25_top_k` | 提高至 15-20 |
| | | | `rag_hybrid_vector_top_k` | 提高至 15-20 |
| | | | `rag_hybrid_base_threshold` | 降低至 0.05-0.08 |
| | | | `rag_similarity_threshold` | 降低至 0.6-0.65 |
| | | | `rag_hybrid_bm25_weight` | 若关键词匹配差，提高至 0.6-0.7 |
| **精度不足** | Precision < 0.75 | 加强过滤与排序 | `rag_reranker_final_k` | 降低至 3-5 |
| | | | `rag_search_score_threshold_hybrid` | 提高至 0.4-0.45 |
| | | | `rag_search_no_match_vector_penalty` | 提高至 0.6-0.7 |
| | | | `rag_hybrid_bm25_weight` | 若噪声来自 BM25，降低至 0.3-0.4 |
| **排序质量差** | MRR < 0.65 | 优化重排序 | `rag_reranker_initial_k` | 提高至 40-50 |
| | | | `fusion_score_boost_for_pageindex` | 开启 PageIndex 后提高至 1.3-1.5 |
| | | | `rag_reranker_model` | 评估切换至更强模型 |
| **综合得分低** | F1 < 0.6 或 NDCG < 0.75 | 平衡召回与精度 | `rag_hybrid_merge_mode` | 切换 OR/AND 模式 |
| | | | `rag_relative_cutoff_ratio` | 调整至 0.4-0.5 |
| **年龄适配差** | 年龄相关 Bad Case > 30% | 调整年龄过滤 | `rag_age_filter_strictness` | 降低至 0.5-0.6 |
| | | | `rag_age_filter_tolerance` | 提高至 3-4 |
| | | | `rag_age_fit_weight` | 提高至 0.4-0.5 |
| **复杂查询失败** | 复杂查询失败率 > 40% | 启用增强功能 | `pageindex_enabled` | 开启 |
| | | | `rag_query_rewrite_enabled` | 开启 |
| | | | `query_router_llm_enabled` | 开启 |

#### 8.3.2 规则引擎实现要求
- **规则配置化**：规则存储在 `rules.json` 的 `rag_tuning_rules` 字段，支持热更新
- **建议优先级排序**：按预期影响幅度排序 (高/中/低)
- **冲突检测算法**：
  1. 收集所有待输出的建议，按参数名分组
  2. 对同一参数的多条建议，检查动作方向是否矛盾（如同时建议"提高"和"降低"）
  3. 若检测到冲突，保留优先级更高的建议（基于指标短板严重程度），丢弃低优先级建议
  4. 输出时标注"已过滤 X 条冲突建议"
- **安全边界**：建议值必须在合理范围内，不得给出极端值（如 bm25_top_k 不得建议 > 50）

### 8.4 历史对比分析：参数变更效果追踪

**核心逻辑**：从历史 TestRun 中提取参数变更与指标变化的关联关系。

#### 8.4.1 数据关联链路
```
TestRun → config_version_id → ConfigVersion → config_snapshot (JSON)
       → previous_config_version_id → 对比差异 → 提取变更参数
       → overall_precision/recall/f1/mrr/ndcg → 计算指标变化
```

#### 8.4.2 匹配策略
- **相似问题匹配**：当前指标短板与历史运行的指标短板相似 (如都是 Recall 低)
- **参数变更匹配**：历史运行中修改过与当前建议相关的参数
- **效果验证**：展示"修改参数 X 从 A 到 B 后，指标 Y 变化了 Z%"

#### 8.4.3 输出格式
```json
{
  "type": "history_reference",
  "reference_runs": [
    {
      "run_id": "run_20260315_001",
      "date": "2026-03-15",
      "changed_params": {
        "rag_hybrid_bm25_top_k": { "from": 10, "to": 15 }
      },
      "metric_changes": {
        "overall_recall": { "from": 0.62, "to": 0.78, "delta": "+0.16" },
        "overall_precision": { "from": 0.85, "to": 0.81, "delta": "-0.04" }
      },
      "conclusion": "提高 bm25_top_k 显著提升召回率，但精度略有下降"
    }
  ]
}
```

### 8.5 LLM-as-Judge 深度诊断：Bad Case 语义分析

**核心逻辑**：对失败的测试用例进行语义分析，找出共性模式和根因。

#### 8.5.1 分析维度
| 维度 | 分析内容 | 输出示例 |
|------|---------|---------|
| **关键词覆盖** | Bad Case 中的关键词是否出现在检索结果中 | "3 个失败案例均包含'前庭觉训练'，但检索结果中该关键词覆盖率仅 12%" |
| **领域集中度** | Bad Case 集中在哪些发展领域 | "70% 失败案例属于'感觉统合'领域，建议检查该领域文档覆盖度" |
| **查询复杂度** | 失败案例的查询类型分布 | "8 个失败案例中 6 个为复杂查询，建议开启查询重写" |
| **年龄分布** | 失败案例的年龄段分布 | "0-2 岁案例失败率 45%，显著高于其他年龄段" |
| **内容相关性** | 检索结果与查询的语义相关度 | "失败案例的平均检索相关度 0.32，远低于通过案例的 0.71" |

#### 8.5.2 Prompt 设计
需通过 PromptManager 管理诊断 Prompt (`rag_tuning_diagnosis`)，包含：

**系统指令**：
```
你是一个 RAG 系统诊断专家。请分析以下失败的测试用例 (Bad Case)，找出共性根因，
并给出具体、可操作的优化建议。

分析维度：
1. 关键词覆盖：Bad Case 中的关键词是否出现在检索结果中
2. 领域集中度：Bad Case 集中在哪些发展领域
3. 查询复杂度：失败案例的查询类型分布
4. 年龄分布：失败案例的年龄段分布
5. 内容相关性：检索结果与查询的语义相关度

要求：
- 建议必须具体可操作（如"提高 bm25_top_k 从 10 到 15"，而非"优化检索"）
- 区分"参数调整"、"功能开关"、"内容补充"三类建议
- 每条建议标注预期效果和置信度
```

**输入格式**（JSON）：
```json
{
  "bad_cases": [
    {
      "query": "前庭觉训练适合几岁开始",
      "domain": "感觉统合",
      "age": 2,
      "expected_keywords": ["前庭觉", "年龄", "训练"],
      "actual_keywords": ["运动", "平衡"],
      "recall": 0.0,
      "retrieved_docs_count": 2,
      "avg_relevance": 0.32
    }
  ],
  "summary_stats": {
    "total_bad_cases": 8,
    "domain_distribution": {"感觉统合": 5, "粗大动作": 2, "精细动作": 1},
    "age_distribution": {"0-2": 4, "3-5": 3, "6-8": 1},
    "complex_query_failure_rate": 0.75
  }
}
```

**输出格式**：JSON 结构化诊断结果（见 8.5.3）

#### 8.5.3 输出格式
```json
{
  "type": "llm_diagnosis",
  "summary": "主要问题为感觉统合领域文档覆盖不足，以及复杂查询处理能力欠缺",
  "findings": [
    {
      "category": "content_coverage",
      "description": "感觉统合相关文档仅 3 篇，占总量 8%，建议补充该领域知识",
      "confidence": 0.85
    },
    {
      "category": "query_complexity",
      "description": "复杂查询失败率 75%，建议开启 PageIndex 和查询重写功能",
      "confidence": 0.78
    }
  ],
  "recommendations": [
    {
      "action": "upload_documents",
      "description": "上传感觉统合相关的专业文档，特别是前庭觉和本体觉训练内容",
      "priority": "high"
    },
    {
      "action": "enable_feature",
      "params": { "pageindex_enabled": true, "rag_query_rewrite_enabled": true },
      "priority": "medium"
    }
  ]
}
```

### 8.6 全量参数分组与触发条件

将 70+ 参数按问题域分为 7 组，每组关联特定的触发条件和建议动作：

| 问题域 | 包含参数 (核心) | 触发条件 | 建议类型 |
|--------|----------------|---------|---------|
| **召回优化** | `bm25_top_k`, `vector_top_k`, `base_threshold`, `similarity_threshold`, `bm25_weight`, `vector_weight` | Recall < 0.7 | 参数值调整 |
| **精度优化** | `reranker_final_k`, `score_threshold_hybrid/vector`, `no_match_vector_penalty`, `bm25_weight` | Precision < 0.75 | 参数值调整 |
| **排序优化** | `reranker_initial_k`, `reranker_model`, `fusion_score_boost`, `reranker_enabled` | MRR < 0.65 | 参数值调整 + 模型切换 |
| **年龄适配** | `age_filter_strictness`, `age_filter_tolerance`, `age_fit_weight` | 年龄相关 Bad Case > 30% | 参数值调整 |
| **分块优化** | `chunk_size`, `chunk_overlap`, `semantic_threshold`, `chapter_max_size` | 内容截断/碎片化 Bad Case > 20% | 参数值调整 + 重新分块 |
| **性能优化** | `max_workers`, `concurrency_limit`, `cache_size`, `cache_ttl` | 平均耗时 > 目标值 | 参数值调整 |
| **功能开关** | `pageindex_enabled`, `query_rewrite_enabled`, `query_router_llm_enabled`, `layered_content_enabled` | 复杂查询失败率 > 40% | 功能开启/关闭 |

### 8.7 API 与前端集成

#### 8.7.1 后端 API

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/v1/rag/test/run/{run_id}/tuning-suggestions` | GET | 获取指定测试运行的调参建议 (包含三层诊断结果) |
| `/api/v1/rag/test/tuning-suggestions/preview` | POST | 预览应用某条建议后的预期指标变化 (基于历史数据模拟) |
| `/api/v1/rag/test/tuning-suggestions/apply` | POST | 一键应用建议参数到当前配置版本 |

#### 8.7.2 前端集成位置

**MVP 阶段（Phase 2C 首期）**：
- **位置 A：评估报告内嵌 (快速建议)**
  - 在 `EvaluationReport` 组件底部增加「调参建议」区块
  - 仅展示规则引擎生成的 2-5 条核心建议
  - 每条建议包含：问题描述、建议动作、预期效果、一键应用按钮
  - 折叠展示历史参考（若有 ≥2 次历史运行）
  - LLM 诊断详情暂不展示（后续迭代）

**后续迭代（Phase 2C 二期）**：
- **位置 B：独立分析面板 (深度分析)**
  - 在 RAG 评估页新增「参数优化」Tab
  - 功能模块：
    - **当前诊断**：展示三层诊断完整结果
    - **参数健康度**：可视化展示各参数组的当前值与推荐范围
    - **历史调参记录**：时间线展示过往参数变更及效果
    - **一键优化**：选择优化目标 (召回优先/精度优先/平衡) 后自动应用建议
    - **A/B 对比**：调参前后指标对比图表

#### 8.7.3 新增前端组件

**MVP 阶段**：
| 组件 | 说明 |
|------|------|
| `TuningSuggestionsPanel.tsx` | 调参建议面板 (报告内嵌，仅规则引擎层) |
| `OneClickOptimize.tsx` | 一键优化组件 |

**后续迭代**：
| 组件 | 说明 |
|------|------|
| `ParameterOptimizerPage.tsx` | 参数优化独立页面 |
| `ParameterHealthChart.tsx` | 参数健康度雷达图 |
| `TuningHistoryTimeline.tsx` | 历史调参时间线 |
| `BeforeAfterComparison.tsx` | 调参前后对比图表 |

## 7. 风险控制与迁移策略

### 7.1 回滚策略
- **配置回滚**：所有配置变更通过 `ConfigManager` 版本控制支持一键回滚
- **提示词回滚**：`PromptManager` 保留所有历史版本，可随时切换至旧版本
- **数据库迁移回滚**：使用 Alembic 管理数据库变更，提供 `alembic downgrade` 脚本
- **功能开关**：关键功能引入 feature flag，支持运行时禁用

### 7.2 灰度发布计划
- **Phase 1 (LLM 多提供商)**：
  1. 先部署新工厂类，默认仍使用 DashScope
  2. 通过配置切换单个非核心场景 (如 query_classification) 到新提供商验证
  3. 逐步切换所有场景，监控错误率和延迟
- **Phase 2A (RAG 评估工作流重塑)**：
  1. 全量同步存量JSON数据到DB，批量验证MRR/NDCG/命中率指标，DB路径与原JSON路径计算结果误差<0.001
  2. 直接切换读写路径为DB，不启用双读/双写过渡模式，所有新数据直接写入DB
  3. 对外API接口`list_test_runs`和`get_test_run`签名保持完全不变，兼容现有调用方
- **Phase 2B (提示词/配置收拢)**：
  1. 提示词迁移按 P0/P1/P2 分批，**每迁移 2-3 个就做一次回归测试**
  2. 魔法值迁移后通过单元测试验证算法行为一致性
- **Phase 2C (智能调参建议引擎)**：
  1. 先开放规则引擎 (无 LLM 成本)，验证建议准确性
  2. 启用历史对比分析，验证数据关联链路
  3. 最后启用 LLM 诊断，监控调用成本和响应质量
- **Phase 3 (LLM 追踪)**：
  1. 先开启异步写入 + 10% 采样率，验证数据完整性
  2. 前端 Trace Viewer 独立部署，不影响现有监控面板
  3. 逐步增加采样率至 100%，增加 Span 覆盖范围

### 7.3 兼容性保障
- **降级机制**：PromptManager 不可用时使用代码内嵌的 fallback 提示词
- **双写过渡**：数据库迁移期间，关键数据同时写入新旧存储，验证一致后再切换读路径
- **监控告警**：配置变更、提示词加载失败、LLM 调用异常时触发告警
- **API 兼容性**：废除 JSON 路径后，`list_test_runs` 和 `get_test_run` API 接口签名保持不变，仅内部实现从 JSON 切换为 DB。若有外部系统依赖旧 API，需在迁移前通知并提供过渡期（至少 2 周）

### 7.4 安全审计 (新增)
- **API Key 存储**：全局提供商凭证中的 `api_key` 在数据库中应加密存储（使用 Fernet 对称加密或 Hashicorp Vault），而非明文
- **热更新权限控制**：配置热更新接口需增加权限校验，仅允许管理员角色修改 LLM 提供商凭证和场景参数
- **Trace 数据脱敏**：`prompt_messages` 和 `completion_message` 中若包含用户个人信息（如儿童姓名），需在写入前脱敏
- **审计日志**：所有配置变更、提示词版本切换、提供商切换操作需记录到 `ConfigAuditLog`，包含操作人、时间、变更内容

### 7.5 文档更新计划 (新增)
每次 Phase 完成后，必须同步更新以下文档：
- `AGENTS.md`：更新系统架构图、Agent 定义、配置系统说明
- `CLAUDE.md`：更新项目结构、核心模块职责、API 端点变更
- `docs/superpowers/specs/`：标记已完成的 Spec 条目
- 变更标记：在文档末尾添加更新记录，格式为 `YYYY-MM-DD: [Phase X] 更新内容摘要`

## 9. 数据库迁移清单 (新增)

以下 Alembic 迁移脚本需按顺序创建和执行：

### Phase 1 迁移
| 迁移脚本 | 操作 | 说明 |
|---------|------|------|
| `001_add_llm_provider_config` | ALTER TABLE `config_snapshots` | 扩展配置快照结构以支持 `llm_providers` 全局凭证 |

### Phase 2A 迁移
| 迁移脚本 | 操作 | 说明 |
|---------|------|------|
| `002_add_mrr_ndcg_to_test_run_result` | ALTER TABLE `test_run_results` | 新增 `mrr` (DECIMAL(10,4)) 和 `ndcg` (DECIMAL(10,4)) 字段 |
| `003_add_deleted_status_to_test_run` | ALTER TABLE `test_runs` | 新增 `deleted_at` (DateTime, nullable) 字段支持软删除 |
| `004_add_export_format_to_test_run` | ALTER TABLE `test_runs` | 新增 `report_export_format` (Enum: markdown/pdf) 字段 |

### Phase 2B 迁移
| 迁移脚本 | 操作 | 说明 |
|---------|------|------|
| `005_extend_prompt_version_variables` | ALTER TABLE `prompt_versions` | 扩展 `variables` 字段以支持更多占位符类型 |

### Phase 3 迁移
| 迁移脚本 | 操作 | 说明 |
|---------|------|------|
| `006_create_traces_table` | CREATE TABLE `traces` | 创建追踪表 (trace_id PK, name, user_id, session_id, metadata, start_time, end_time, total_duration_ms, total_tokens, total_cost, status, created_at) |
| `007_extend_llm_call_logs_for_tracing` | ALTER TABLE `llm_call_logs` | 新增 trace_id, span_id, parent_span_id, prompt_messages (TEXT), completion_message (TEXT), call_parameters (JSON), model_parameters (JSON), cost (DECIMAL), tags (JSON), completion_start_time_ms, level (Enum) |
| `008_add_trace_indexes` | CREATE INDEX | 为 trace_id, span_id, user_id, created_at 建立索引 |

**回滚脚本**：每个迁移脚本需提供对应的 `downgrade()` 方法，支持 `alembic downgrade -1` 回滚。

## 10. 实施待办清单

### Phase 1: LLM 多提供商 + 热配置

#### 1.1 配置层改造
- [ ] 1.1.1 扩展 `src/config/modules/models/llm.py`：新增 `llm_providers` 全局凭证配置结构
- [ ] 1.1.2 扩展 `src/config/modules/models/llm.py`：将 8 个场景的 `model_*` 字段改为结构化配置 (provider + model + temperature + max_tokens + top_p)
- [ ] 1.1.3 扩展 `src/config/modules/models/embedding.py`：新增 `embedding_provider` 字段
- [ ] 1.1.4 将所有 LLM 配置项从冷更新名单中移除，接入热更新机制

#### 1.2 工厂类重构
- [ ] 1.2.1 创建 Provider Registry 映射表 `(provider, framework) -> LLM class`
- [ ] 1.2.2 重构 `LLMServiceFactory.create()` 接收 `provider` 参数
- [ ] 1.2.3 实现凭证自动注入逻辑 (从全局配置提取 api_key/base_url)
- [ ] 1.2.4 实现实例清理策略 (等待中请求处理、延迟清理、超时强制清理、状态标记、清理日志)
- [ ] 1.2.5 创建 `EmbeddingFactory` 支持多提供商

#### 1.3 VL 解析与 ML 评分抽象
- [ ] 1.3.1 重构 `src/core/parsers.py`：移除 `dashscope.MultiModalConversation.call()`，改用提供商工厂
- [ ] 1.3.2 重构 `src/core/ml/qwen_scorer.py`：移除 DashScope HTTP 直调，改用提供商工厂

#### 1.4 依赖与调用点改造
- [ ] 1.4.1 在 `pyproject.toml` 中新增 OpenAI/Anthropic/Ollama 相关依赖包
- [ ] 1.4.2 改造 15+ 调用点文件中的 `settings.dashscope_api_key` 检查为 provider-agnostic 方式
- [ ] 1.4.3 改造所有 `LLMServiceFactory.create()` 调用，传入 provider 参数或依赖配置驱动

#### 1.5 前端适配
- [ ] 1.5.1 升级 `/system-config` 页面，支持全局提供商凭证配置表单
- [ ] 1.5.2 升级 `/system-config` 页面，支持场景化模型配置表单 (provider 选择 + model 输入 + 参数调节)

#### 1.6 验证与测试
- [ ] 1.6.1 编写单元测试验证 Provider Registry 映射正确性
- [ ] 1.6.2 编写集成测试验证热更新机制 (配置变更 -> 实例重建)
- [ ] 1.6.3 灰度验证：切换 query_classification 场景到新提供商，监控错误率和延迟
- [ ] 1.6.4 性能基准测试：对比各提供商的延迟和 Token 消耗，建立基线数据

#### 1.7 错误处理与降级策略 (新增)
- [ ] 1.7.1 实现提供商不可用时的自动降级逻辑（如 OpenAI 超时 → 降级到 DashScope）
- [ ] 1.7.2 为每个场景配置 `fallback_provider` 字段，指定备用提供商
- [ ] 1.7.3 实现降级事件告警，通知管理员主提供商异常
- [ ] 1.7.4 编写集成测试验证降级链路正确性

---

### Phase 2A: RAG 评估工作流重塑

#### 2A.1 执行路径统一
- [ ] 2A.1.1 扩展 `TestRunResult` 模型：新增 `mrr` 和 `ndcg` 字段
- [ ] 2A.1.2 创建 Alembic 迁移脚本 `002_add_mrr_ndcg_to_test_run_result`
- [ ] 2A.1.3 重构 `list_test_runs` 和 `get_test_run` 方法：从 JSON 文件读取改为 MySQL 读取（保留文件路径作为 fallback，双读模式过渡）
- [ ] 2A.1.4 统一执行入口：确保所有测试执行通过 `POST /rag/test/run` 使用 `RetrievalService.search()`
- [ ] 2A.1.5 在 DB 执行路径中补充 MRR/NDCG 指标计算
- [ ] 2A.1.6 实现 TestRun 软删除逻辑（标记 `deleted_at`，7 天后物理删除）
- [ ] 2A.1.7 测试用例草稿生成优化
  - [ ] 2A.1.7.1 扩展`src/config/modules/rag/testing.py`：新增5个测试用例草稿生成相关配置项
  - [ ] 2A.1.7.2 优化`test_case_draft_generation`提示词：增加多维度生成要求、批量生成要求
  - [ ] 2A.1.7.3 实现草稿生成去重、完整性校验、相关性校验逻辑
  - [ ] 2A.1.7.4 实现并行批量生成逻辑，支持断点续传功能
  - [ ] 2A.1.7.5 验证单篇文档生成100条草稿的速度提升效果（生成耗时较原版本提升≥5倍）
  - [ ] 2A.1.7.6 验证生成草稿的多维度覆盖率≥90%，重复率≤5%

#### 2A.2 前端 UI 修复与增强
- [ ] 2A.2.1 修复 `RagEvaluationPage.tsx`：接通 `getTestSets` API，传入真实数据
- [ ] 2A.2.2 实现 Case Picker 组件：支持从正式案例库/草稿库勾选、批量操作、反向查询
- [ ] 2A.2.3 增强测试集详情页：展示已关联案例列表，支持移除案例
- [ ] 2A.2.4 实现报告导出功能：Markdown 导出（首期）+ PDF 导出（引入 weasyprint）

#### 2A.3 验证与测试
- [ ] 2A.3.1 验证 DB 路径与原有文件路径的指标一致性
- [ ] 2A.3.2 验证 MRR/NDCG 计算正确性
- [ ] 2A.3.3 验证软删除和级联删除逻辑

---

### Phase 2B: 提示词/配置收拢

#### 2B.1 提示词迁移 (P0 - 核心评估流程)
- [ ] 2B.1.1 提取 `assessment_system` 提示词至 PromptManager，更新 `assessment.py` 调用
- [ ] 2B.1.2 提取 `reporting_system` 提示词至 PromptManager，更新 `reporting.py` 调用
- [ ] 2B.1.3 提取 `validation_system`、`intensity_inference`、`category_inference` 至 PromptManager，更新 `validation.py` 调用
- [ ] 2B.1.4 为 P0 提示词配置 fallback 值
- [ ] 2B.1.5 **回归测试**：验证核心评估流程功能正常

#### 2B.2 提示词迁移 (P1 - RAG 检索)
- [ ] 2B.2.1 提取 `rag_query_template`、`query_rewrite`、`synonym_expansion` 至 PromptManager
- [ ] 2B.2.2 提取 `query_classification` 提示词至 PromptManager，更新 `query_router.py` 调用
- [ ] 2B.2.3 为 P1 提示词配置 fallback 值
- [ ] 2B.2.4 **回归测试**：验证 RAG 检索功能正常

#### 2B.3 提示词迁移 (P2 - 元数据与内容生成)
- [ ] 2B.3.1 提取 `metadata_extraction` 至 PromptManager，更新 `metadata_extractor.py` 调用
- [ ] 2B.3.2 提取 `test_case_draft_generation` 至 PromptManager
- [ ] 2B.3.3 提取 4 个 `layered_content_*` 提示词至 PromptManager，更新 `layered_content_generator.py` 调用
- [ ] 2B.3.4 为 P2 提示词配置 fallback 值
- [ ] 2B.3.5 **回归测试**：验证文档导入和分层内容生成功能正常

#### 2B.4 魔法值迁移 (P0 - LLM 参数)
- [ ] 2B.4.1 在配置模块中新增 `llm.*.temperature` 和 `llm.*.max_tokens` 配置项
- [ ] 2B.4.2 移除 15+ 文件中硬编码的 temperature 和 max_tokens，改为从配置读取
- [ ] 2B.4.3 验证所有 LLM 调用参数正确加载

#### 2B.5 魔法值迁移 (P1 - RAG 阈值)
- [ ] 2B.5.1 在 `rag_` 配置模块中新增去重、评分、年龄适配相关配置项
- [ ] 2B.5.2 移除 `retrieval_service.py`、`scoring.py` 中的硬编码阈值
- [ ] 2B.5.3 通过单元测试验证算法行为一致性

#### 2B.6 魔法值迁移 (P2 - 文档处理与业务规则)
- [ ] 2B.6.1 在 `rag_` 配置模块中新增元数据、分块相关配置项
- [ ] 2B.6.2 将 `age_filter.py` 年龄段参数提取至 `rules.json`
- [ ] 2B.6.3 将 `child_development_engine.py` 年龄边界和推荐规则提取至 `rules.json`
- [ ] 2B.6.4 更新代码从 ConfigManager/rules.json 读取配置

#### 2B.7 验证与测试
- [ ] 2B.7.1 每迁移 2-3 个提示词后执行回归测试
- [ ] 2B.7.2 魔法值迁移后通过单元测试验证算法行为一致性

---

### Phase 2C: 智能调参建议引擎

#### 2C.1 规则引擎（MVP 首期）
- [ ] 2C.1.1 在 `rules.json` 中新增 `rag_tuning_rules` 规则配置
- [ ] 2C.1.2 实现规则引擎核心逻辑：指标 → 问题类型 → 参数建议映射
- [ ] 2C.1.3 实现建议优先级排序和冲突检测算法
- [ ] 2C.1.4 实现安全边界校验，确保建议值在合理范围内
- [ ] 2C.1.5 编写单元测试验证各指标阈值触发正确的参数建议
- [ ] 2C.1.6 实现 `GET /api/v1/rag/test/run/{run_id}/tuning-suggestions` 接口（仅规则引擎层）
- [ ] 2C.1.7 创建 `TuningSuggestionsPanel.tsx` 组件（报告内嵌）
- [ ] 2C.1.8 创建 `OneClickOptimize.tsx` 组件（一键优化）
- [ ] 2C.1.9 在 `EvaluationReport` 中集成调参建议区块
- [ ] 2C.1.10 实现一键应用参数后的配置热更新提示

#### 2C.2 历史对比分析（二期）
- [ ] 2C.2.1 实现 TestRun 与 ConfigVersion 的关联查询逻辑
- [ ] 2C.2.2 实现配置版本差异对比，提取变更参数列表
- [ ] 2C.2.3 实现相似问题匹配算法 (基于指标短板相似度)
- [ ] 2C.2.4 实现历史参考建议的格式化输出
- [ ] 2C.2.5 编写集成测试验证历史对比链路完整性
- [ ] 2C.2.6 在 `TuningSuggestionsPanel` 中折叠展示历史参考

#### 2C.3 LLM 诊断（三期）
- [ ] 2C.3.1 在 PromptManager 中新增 `rag_tuning_diagnosis` 提示词
- [ ] 2C.3.2 实现 Bad Case 语义分析逻辑 (关键词覆盖、领域集中度、查询复杂度等)
- [ ] 2C.3.3 实现 LLM 诊断结果的 JSON 结构化输出
- [ ] 2C.3.4 实现诊断置信度计算和降级策略
- [ ] 2C.3.5 验证 LLM 诊断在 Bad Case ≥ 3 时触发

#### 2C.4 后端 API 扩展（二期/三期）
- [ ] 2C.4.1 实现 `POST /api/v1/rag/test/tuning-suggestions/preview` 接口
- [ ] 2C.4.2 实现 `POST /api/v1/rag/test/tuning-suggestions/apply` 接口
- [ ] 2C.4.3 实现三层诊断结果的聚合与编排逻辑
- [ ] 2C.4.4 编写 API 测试验证各接口返回格式正确

#### 2C.5 前端深度分析（三期）
- [ ] 2C.5.1 创建 `ParameterOptimizerPage.tsx` 组件 (独立优化页)
- [ ] 2C.5.2 创建 `ParameterHealthChart.tsx` 组件 (参数健康度雷达图)
- [ ] 2C.5.3 创建 `TuningHistoryTimeline.tsx` 组件 (历史调参时间线)
- [ ] 2C.5.4 创建 `BeforeAfterComparison.tsx` 组件 (调参前后对比)
- [ ] 2C.5.5 在 RAG 评估页新增「参数优化」Tab 并集成各组件

---

### Phase 3: LLM 调用追踪

#### 3.1 数据模型与迁移
- [ ] 3.1.1 创建 `Trace` SQLAlchemy 模型 (`traces` 表)
- [ ] 3.1.2 扩展 `LLMCallLog` 模型：新增 trace_id、span_id、parent_span_id、prompt_messages、completion_message、call_parameters 等字段
- [ ] 3.1.3 创建 Alembic 迁移脚本
- [ ] 3.1.4 创建 `TraceRepository` 和更新 `LLMCallLogRepository`

#### 3.2 调用链路集成
- [ ] 3.2.1 实现 Trace/Span 上下文传递机制 (使用 contextvars)
- [ ] 3.2.2 在 LangGraph 工作流节点前后集成 Span 创建/关闭逻辑
- [ ] 3.2.3 在 `RagTestManager.execute_batch` 中为每个测试用例创建独立 Trace
- [ ] 3.2.4 实现异步写入队列，不阻塞主流程

#### 3.3 性能优化
- [ ] 3.3.1 实现 prompt_messages 和 completion_message 截断存储 (默认 8000 字符，可配置 `trace_truncate_length`)
- [ ] 3.3.2 实现 TTL 清理机制 (默认保留 30 天)
- [ ] 3.3.3 为 trace_id、span_id、user_id、created_at 建立索引
- [ ] 3.3.4 实现采样策略 (trace_sample_rate + trace_error_sample_rate)

#### 3.4 后端 API 开发
- [ ] 3.4.1 实现 `GET /api/v1/monitoring/traces` 分页查询接口
- [ ] 3.4.2 实现 `GET /api/v1/monitoring/traces/{trace_id}` 详情接口 (含 Span 层级树)
- [ ] 3.4.3 实现 `GET /api/v1/monitoring/traces/{trace_id}/spans/{span_id}` Span 详情接口
- [ ] 3.4.4 实现 `GET /api/v1/monitoring/logs` 高级筛选接口
- [ ] 3.4.5 实现 `GET /api/v1/monitoring/cost` 成本分析接口
- [ ] 3.4.6 实现 `GET /api/v1/monitoring/latency` 延迟分布接口 (P50/P95/P99)
- [ ] 3.4.7 实现 `GET /api/v1/monitoring/errors` 错误分析接口

#### 3.5 前端 Trace Viewer 开发
- [ ] 3.5.1 创建 `TraceListView.tsx` 组件 (追踪列表表格)
- [ ] 3.5.2 创建 `TraceDetailDrawer.tsx` 组件 (追踪详情抽屉)
- [ ] 3.5.3 创建 `SpanTreeView.tsx` 组件 (Span 层级树)
- [ ] 3.5.4 创建 `SpanDetailPanel.tsx` 组件 (Span 详情面板，支持 Markdown 渲染)
- [ ] 3.5.5 创建 `TraceFilterBar.tsx` 组件 (高级筛选器)
- [ ] 3.5.6 创建 `CostAnalysisDashboard.tsx` 组件 (成本分析面板)
- [ ] 3.5.7 创建 `LatencyChart.tsx` 组件 (延迟分布图表)
- [ ] 3.5.8 在 `LLMMonitoringDashboard.tsx` 中集成 "调用追踪" 标签页

#### 3.6 验证与测试
- [ ] 3.6.1 验证 Trace/Span 层级关系正确性
- [ ] 3.6.2 验证异步写入不阻塞主流程
- [ ] 3.6.3 验证前端 Trace Viewer 各组件功能正常
- [ ] 3.6.4 性能测试：验证大量写入时数据库负载可控
- [ ] 3.6.5 性能基准测试：多提供商切换后，验证延迟无回归（对比 DashScope 基线）