# ⚠️ 核心工作原则 (不可忽略)

【以第一性原理！从原始需求和问题本质出发，不从惯例或模板出发。
1. 不要假设我清楚自己想要什么。动机或目标不清晰时，停下来讨论。
2. 目标清晰但路径不是最短的，直接告诉我并建议更好的办法。
3. 遇到问题追根因，不打补丁。每个决策都要能回答"为什么"。
4. 输出说重点，砍掉一切不改变决策的信息。】

【文件位置锁定】
- `CLAUDE.md` 必须始终位于项目根目录下，禁止移动。
- 这是 AI 助手介入项目的**唯一全局规则与入口**。
- 系统架构、业务逻辑、配置细节等所有底层文档统一存放在 `.ai/` 目录下。
- 任何系统级架构改动，必须同步更新 `.ai/` 目录下的相应子文件。
- 除 `CLAUDE.md` 和 `.ai/` 目录外，其他文档（如 `docs/`）可能随时过期，不作为权威参考。设计提案类文档（如 `docs/architecture/`）明确标注实施状态后方可使用。

---

# 🤖 AI 上下文路由字典 (Context Map)

为了保持 AI 专注与避免幻觉，系统的所有底层架构、业务逻辑与配置细节已剥离至专属的 `.ai/` 目录。

**【强制要求】当执行特定领域任务时，你必须主动调用 `Read` 工具读取对应的领域文档：**

| 领域 / 任务 | 查阅哪个文件/目录？ | 包含哪些信息？ |
|-------------|----------------|----------------|
| **快速逻辑定位** | `.ai/business_logic_map.md` | 各大业务模块（Agent/RAG/基建/测试）的核心逻辑概述与具体代码文件入口。 |
| **Agent 业务编排** | `.ai/agents_workflow.md` | LangGraph 状态管理、NodePre 到 Node5 节点职责与输入输出 |
| **知识问答模块** | `core/knowledge_qa/` + `service/knowledge_qa_service.py` | 独立 LangGraph 编排的知识问答系统，含知识图谱（graph/）、13个业务节点、子 Agent、工具集 |
| **知识问答架构重设计** | `docs/architecture/00-审查报告与方案概述.md` | 🟡 设计提案（0% 已实施）— Neo4j 知识图谱 + Agent 三层改造方案。**非权威现状**，实施后应迁移至 `.ai/`。 |
| **系统架构与设计** | `.ai/architecture.md` | 多层架构总览图、各微服务或子系统的模块交互关系、数据流向 |
| **基础设施与配置** | `.ai/infrastructure.md` | 数据库(MySQL/Redis)参数、DI注入规范、LLM模型工厂、提示词管理 |
| **数据库初始化**   | `.ai/full_init_script_mysql57.sql` | 完整的 MySQL 5.7 DDL 脚本，包含建库、21张业务建表语句（无外键约束，采用弱关联） |
| **RAG 知识库检索** | `.ai/rag_pipeline.md` | RAG 核心模块、双流水线解析、向量库(Chroma)检索策略、API端点 |
| **协同开发规范**   | `.ai/sdd_tdd_workflow.md`| SDD+TDD 工作流 SOP、红绿重构规则、用于生成的 Prompt 模板 |
| **SDD+TDD实践指南**| `.ai/sdd_tdd_practice_guide.md` | 深入解析 SDD+TDD 融合实践的核心概念、全流程落地标准及避坑指南 |
| **RAG 完整技术文档**| `.ai/rag_pipeline.md` | RAG 系统完整的技术细节、双流水线架构与 API 规范 |
| **统一响应与异常规范**| `.ai/unified-api-response-and-error-handling.md` | 实体类管理、类拆分、冗余消除、统一响应格式、异常处理、错误码规范 |

---

# 📌 项目宏观概览与技术栈

**儿童发展评估 Agent** 是一个基于 AI 的多智能体系统，根据儿童的发展画像评估其运动计划。该系统使用 **LangGraph** 进行编排，采用前后端完全解耦架构。核心能力包含：评估 Agent（6节点 LangGraph 流水线）、知识问答 Agent（13节点 + 知识图谱）、RAG 知识检索（双流水线混合检索）、6层校验诊断引擎、以及多提供商 LLM 热切换支持。

## 技术栈
- **语言**: Python 3.13, TypeScript 5.3
- **核心编排**: LangGraph 1.1.0, LangChain 1.2.11, LlamaIndex 0.14.16
- **大模型支持**: DashScope, OpenAI, Anthropic, DeepSeek, Ollama
- **后端基建**: FastAPI 0.135.1, SQLAlchemy 2.0 (MySQL 5.7), Redis 7.0, Chroma (本地向量库), SSE 推送, Prometheus 指标收集
- **ML/评分**: XGBoost, SHAP, scikit-learn (AHP+ML 融合评分)
- **NLP**: jieba (中文分词), datasketch (MinHash 去重)
- **文档解析**: PyMuPDF, EbookLib, BeautifulSoup, WeasyPrint (PDF 报告生成)
- **DI/调度**: injector (依赖注入), APScheduler (定时任务)
- **缓存/过滤**: cachetools (LRU), pybloom-live (布隆过滤器)
- **前端架构**: React 19.2.4, Vite 6.4, Ant Design 6.3.2, @ant-design/pro-components 3.1.11, @ant-design/charts 2.6, Zustand 5, React Router 7 (react-router-dom 7.13), TanStack Query 5
- **前端测试**: Vitest 4.1, React Testing Library 16.3
- **包管理**: uv (后端), npm (前端)
- **前端路径别名**: `@` → `src/`, `@app` → `src/app/`, `@pages` → `src/pages/`, `@features` → `src/features/`, `@entities` → `src/entities/`, `@shared` → `src/shared/`（配置于 `frontend/vite.config.ts`）

## 后端目录结构
```
backend/src/
├── api/                    # API 基础设施
│   ├── json_response.py    # 统一 JSON 响应类
│   └── sse.py              # SSE 推送基础设施
├── data/                   # 静态数据文件（术语表/同义词/里程碑/测试集/运动清单/jieba词典/敏感词）
├── config/                 # 配置系统
│   ├── core/               # 配置基础设施（管理器、持久化、事件）
│   ├── modules/            # 按功能域拆分的配置模块
│   │   ├── models/         # LLM/Embedding/ML 评分配置模块
│   │   └── rag/            # RAG 配置子模块（分块/检索/向量化/测试/管道）
│   └── rules/              # 业务规则配置层
├── controller/             # API 控制器层
│   ├── rag_eval/           # RAG 评估子控制器（8个：case/draft/metric/report/run/snapshot/tuning + registry）
│   ├── config_controller.py
│   ├── config_health_controller.py
│   ├── config_management_controller.py
│   ├── health_controller.py
│   ├── knowledge_qa_controller.py
│   ├── monitoring_controller.py
│   ├── prompt_management_controller.py
│   ├── rag_controller.py
│   └── task_controller.py
├── core/                   # 核心业务逻辑
│   ├── knowledge_qa/       # 知识问答模块（独立 LangGraph 编排）
│   │   ├── graph/          # 知识图谱（构建/社区/抽取/遍历/重建/管道）
│   │   ├── nodes/          # 13个业务节点（分析/识别/匹配/推荐/生成/校验等）
│   │   ├── prompts/        # 提示词模板
│   │   ├── _assembly.py    # 组装逻辑
│   │   ├── sub_agents.py   # 子 Agent 定义
│   │   └── tools.py        # Agent 工具集
│   ├── llm/                # LLM 工厂与适配器
│   │   ├── adapters/       # 框架适配器（LangChain/LlamaIndex/DashScope/多模态）
│   │   ├── factory.py      # LLM 服务工厂
│   │   ├── embedding_factory.py
│   │   ├── reranker_factory.py    # Reranker 工厂
│   │   ├── base.py         # LLM 基类
│   │   ├── config_validator.py    # 配置校验
│   │   ├── log_collector.py       # LLM 日志收集
│   │   └── provider_registry.py   # Provider 注册表
│   ├── tracing/            # 全链路追踪系统
│   │   ├── writer.py       # 异步追踪写入器
│   │   ├── context.py      # 追踪上下文管理
│   │   ├── cost.py         # 成本计算
│   │   ├── cleanup.py      # 追踪数据清理
│   │   ├── langgraph_middleware.py  # LangGraph 追踪中间件
│   │   └── truncation.py   # 追踪数据截断
│   ├── rag/                # RAG 核心模块
│   ├── metadata/           # 文档元数据处理
│   ├── ml/                 # ML 评分引擎
│   ├── nodes/              # LangGraph 节点（评估 Agent）
│   ├── pipeline/           # RAG 查询流水线
│   │   ├── orchestrator.py # 流水线编排器
│   │   └── steps/          # 流水线步骤（缓存/去重/混合检索/页面增强/查询改写/路由/重排/融合/同义词扩展）
│   ├── prompt/             # 提示词管理（manager + validator）
│   ├── prompt_impl/        # 提示词实现层（facade + ab_test + initializer + storage）
│   └── config/             # 配置缓存
├── middleware/              # 中间件层
│   ├── exception_handler.py # 全局异常处理
│   ├── response_wrapper.py  # 响应包装中间件
│   └── trace_middleware.py  # 追踪中间件
├── models/                 # SQLAlchemy 数据模型
│   ├── rag_eval/           # RAG 评估模型（11个：draft/test_case/test_run/test_set/snapshot/report/tuning/config/enums等）
│   ├── config.py / document.py / graph.py / monitor.py / trace.py
│   └── prompt_version.py / prompt_metadata.py / prompt_enums.py
├── repository/             # 数据访问层
│   ├── rag_eval/           # RAG 评估仓库（11个）
│   ├── base.py             # 泛型 CRUD 基类
│   ├── config_repository.py / document_repository.py
│   ├── graph_repository.py / monitor_repository.py
├── schemas/                # Pydantic 实体类
│   ├── rag_eval/           # RAG 评估实体（diagnosis/draft/metrics/report/snapshot/test_case/test_run/test_set/tuning）
│   ├── assessment.py / auth.py / config.py / knowledge_qa.py
│   ├── llm.py / prompt.py / metadata.py / ml.py / monitoring.py
│   └── query.py / rag.py / task.py / events.py / common.py
├── service/                # 业务服务层
│   ├── rag_eval/           # RAG 评估服务
│   │   ├── case/           # 测试用例服务（facade + case_service + set_service）
│   │   ├── draft/          # 草稿服务（facade + generator + deduplicator + book_analyzer + faithfulness_checker）
│   │   ├── metrics/        # 指标服务
│   │   │   ├── diagnosis/  # 6层诊断引擎（layer1_rules ~ layer6_regression + orchestrator）
│   │   │   └── scoring/    # 评分引擎（retrieval/generation/system + calculators 5个）
│   │   ├── report/         # 报告服务（builder + exporter + markdown_renderer + trend_analyzer）
│   │   ├── run/            # 运行服务（batch_runner + executor + result_processor + snapshot_manager）
│   │   ├── tuning/         # 调优服务（advisor + config_changer + conflict_detector）
│   │   └── orchestrator.py # RAG 评估编排器
│   ├── retrieval/          # 检索服务
│   ├── document_ingestion/ # 文档导入服务
│   ├── cache/              # 缓存服务
│   ├── index_manager/      # 索引管理服务
│   ├── knowledge_qa_service.py  # 知识问答服务
│   └── [其他独立服务]      # alert/audit/config_health/content_audit/document_manager/monitoring/rag/trace 等
├── templates/              # 模板文件
│   └── reports/            # 报告模板（HTML for WeasyPrint）
└── utils/                  # 工具函数
    ├── exceptions.py       # 异常基类（AppException 等）
    ├── error_codes.py      # 错误码定义
    ├── response.py / db.py / di.py / logger.py
    ├── auth_helpers.py / crypto.py / hash_utils.py
    ├── file_ops.py / orm_mapper.py / serializers.py
    ├── embedding_helper.py / similarity.py / text_cleaner.py
    ├── http_client.py / id_generator.py / time_utils.py
```

## 前端目录结构
```
frontend/src/
├── api/                    # API 客户端层
│   ├── assessment/         # 评估 API
│   ├── config/             # 配置 API
│   ├── documents/          # 文档管理 API
│   ├── health/             # 健康检查 API
│   ├── knowledge/          # 知识搜索 API
│   ├── monitoring/         # 监控 API
│   ├── rag-eval/           # RAG 评估 API（10个文件：cases/drafts/metrics/prompts/reports/runs/snapshots/tuning/client/index）
│   └── tracing.ts          # 链路追踪 API
├── components/             # 通用组件
│   ├── assessment/         # 评估组件（AssessmentForm, ReportViewer）
│   ├── config/             # 配置组件（19个：AccordionPanel/ConfigCard/DiffView/DynamicForm/Sidebar/WizardMode等）
│   ├── documents/          # 文档组件（DocumentList, DocumentUploader, TaskProgressList）
│   ├── knowledge/          # 知识搜索组件（SearchInput, SearchResultList, ResultDetailModal）
│   ├── monitoring/         # 监控组件（CostAnalysis, LatencyChart, SpanDetail, TraceFilter等 8个）
│   ├── progress/           # 进度组件（ProgressList, configs, hooks）
│   └── ui/                 # 通用 UI 原子组件（EmptyState, ErrorBoundary, LoadingSpinner）
├── entities/               # 业务实体类型
│   ├── assessment/         # 评估实体
│   ├── rag-eval/           # RAG 评估实体（constants, enums, mappers, types + 测试）
│   └── tracing/            # 链路追踪实体
├── features/               # 业务特性层
│   ├── assessment/         # 评估特性（hooks/, pages/）
│   ├── config/             # 系统配置特性（hooks/, services/, stores/）
│   ├── documents/          # 知识库特性（hooks/, pages/）
│   ├── knowledge/          # 搜索特性（hooks/, pages/）
│   ├── knowledge-qa/       # 知识问答特性（components/, hooks/, pages/, stores/, types/）
│   ├── monitoring/         # LLM 监控特性
│   └── rag-eval/           # RAG 评估特性
│       ├── pages/          # 12个页面（Draft/PromptList/PromptEdit/PromptSandbox/PromptComparison/Run/TestCase/TestSet/Report/ReportDetail/Tuning/Main）
│       ├── components/     # 业务组件（common/diagnosis/draft/metrics/report/test-set/tuning）
│       ├── hooks/          # 13个业务 Hooks
│       ├── stores/         # 3个 Zustand Store
│       └── utils/          # 工具函数
├── lib/                    # 全局库（queryClient - TanStack Query 配置）
├── pages/                  # 独立页面（BookChunksPage, SystemConfigPage）
├── router/                 # 路由配置
├── shared/                 # 共享层
│   ├── api/                # 通用 API 工具（client）
│   ├── hooks/              # 通用 Hooks（useDebounce, usePagination, useSSE）
│   ├── lib/                # 通用库（constants, formatters, highlight, notification, validators）
│   ├── types/              # 通用类型（sse）
│   └── ui/                 # 共享 UI（DiffViewer）
└── app/                    # 应用根组件（含 styles/）
```

## 常用开发命令
- **后端**: `cd backend && uv sync && uv run start` 或 `uv run python src/server.py`
- **后端测试**: `cd backend && uv run pytest`
- **前端**: `cd frontend && npm install && npm run dev`
- **前端测试**: `cd frontend && npm run test`
- **前端类型检查**: `cd frontend && npm run typecheck`
- **前端代码规范**: `cd frontend && npm run lint`
- **Docker 部署**: `docker-compose up -d`（后端容器，端口 **51002**，使用 `backend/Dockerfile` 两阶段构建，资源限制 4GB/2CPU）

---

# 🏗️ 核心架构与开发约束

1. **前后端解耦**: 项目架构要求前后端完全解耦，后端仅提供 API 服务（及 SPA 回退路由），不包含任何前端业务路由逻辑。
2. **配置管理规范**: 
   - **绝对禁止代码硬编码**。所有可配置参数定义在数据库或集中式配置中心。
   - **配置优先级（严格）**：MySQL 数据库（主） > `.env` 文件（仅兜底）。业务配置必须优先从 MySQL 读取，`.env` 仅在数据库未配置或启动初始化时使用。
   - **`.env` 兜底规则**：
     - `.env` 保留所有业务配置的默认值，确保系统无数据库时仍可启动
     - 凭证类配置（API Key 等）必须在 `.env` 中定义兜底值
     - 基础设施配置（DATABASE_URL、REDIS_URL 等）仅存在于 `.env`
     - 前端配置页面修改配置后，写入 MySQL，不修改 `.env`
   - 在多实例部署架构中，动态编辑（如提示词、配置）必须使用 MySQL 共享存储，**禁止直接写入本地 JSON 文件**。
   - 系统全局配置页面通过独立路由 `/system-config` 访问。
3. **依赖管理**: 后端依赖只允许在 `pyproject.toml` 中声明，使用 `uv add`。前端使用 `package.json`。
4. **代码风格**: Python 遵循 PEP 8，使用强类型注解；前端使用 TS 严格模式。**所有代码注释必须全中文**（包括函数说明、行内注释、TODO标记等）。
5. **实体类集中管理（强制）**:
   - **绝对禁止**在 `service/`、`controller/`、`core/` 中定义 `class xxx(BaseModel)`。
   - 所有 Pydantic 实体类必须统一放置在 `backend/src/schemas/` 目录下，按业务模块组织（如 `schemas/assessment.py`、`schemas/rag.py`）。
   - 对于实体数量较多的复杂模块（如 RAG 评估重构），允许使用子目录模式（如 `schemas/rag_eval/draft.py`、`schemas/rag_eval/test_case.py`），但必须在 `schemas/rag_eval/__init__.py` 中统一导出。
6. **类职责拆分（强制）**: 
   - 单类不超过 **500 行**（含空行和注释），违反则必须拆分。
   - 使用门面模式（Facade）对外提供统一 API，内部协调子服务。
7. **冗余代码消除（强制）**: 
   - 禁止重复定义相同功能的函数，必须提取至 `utils/` 目录下的对应工具模块。
   - 高频重复模式：Session 管理、错误处理、模型序列化、文件操作、时间处理。
8. **统一响应与异常（强制）**: 
   - 所有接口返回统一格式：`{code: 0, message: "success", data: {...}}`（成功）或 `{code, message, error_code, details}`（错误）。
   - 保持 HTTP 语义（200/4xx/5xx），业务错误码采用双字段：`code`（数字）+ `error_code`（字符串）。
   - 所有业务异常必须继承 `AppException`，禁止直接使用 `HTTPException`。

> 以上规范的完整细则参见：[统一响应与异常处理规范](.ai/unified-api-response-and-error-handling.md)
9. **零迁移原则（强制）**: 
   - **项目未上线，不存在历史兼容问题**。
   - 修改代码时**直接删除旧代码**，禁止保留向后兼容层、废弃标记、迁移脚本。
   - 数据库变更**直接修改 DDL**，禁止编写 Alembic 迁移脚本（up/down）。
   - 前端路由/组件变更**直接替换**，禁止保留旧路由重定向或兼容逻辑。
   - 配置/提示词变更**直接覆盖**，禁止保留旧字段或降级逻辑。
   - 唯一例外：第三方 API 契约变更需确认外部依赖方已同步更新。

---

# 💡 核心踩坑与最佳实践 (基于系统记忆)

在开发与修复问题时，必须注意以下已验证的规则：

### 1. 数据库与 ORM (SQLAlchemy)
- **Enum 插入约束**: 向 MySQL 插入 Enum 时，必须使用 SQLAlchemy Enum 类成员（如 `TestDomain.SENSORY_INTEGRATION`），不要传字符串，否则会导致 `DataError (Data truncated)`。
- **Enum 映射规则**: 定义 SQLAlchemy 模型时，必须显式传递 `values_callable=lambda obj: [e.value for e in obj]`，防止因大小写导致 `LookupError`。

### 2. 异步编程与 FastAPI
- **SSE 推送异常**: 在通过 `AsyncTaskManager` 或 `SSEPublisher` 推送 SSE 结果时，确保结果被 `jsonable_encoder` 处理为 JSON 序列化对象，直接传 Pydantic 或 ORM 模型会导致 ASGI `ExceptionGroup` 崩溃。
- **异步任务签名**: 通过 `AsyncTaskManager.start_task` 触发异步任务时，关键字参数必须与目标函数签名完全匹配；后台任务严禁抛出未捕获异常，防止 `Task exception was never retrieved`。

### 3. RAG 与 LlamaIndex
- **ChromaDB 距离度量**: 使用输出 Cosine Similarity 的 Embedding 模型（如 DashScope）时，创建 Chroma collection 必须指定 `metadata={'hnsw:space': 'cosine'}`，否则分数计算异常。
- **docstore 持久化**: 使用自定义 Chroma 库时，必须在创建 `VectorStoreIndex` 时传入 `store_nodes_override=True`，否则 `docstore.json` 为空，导致依赖 docstore 的检索器（如 BM25）失效。
- **目录隔离**: LlamaIndex `StorageContext` 的 `persist_dir` 必须使用独立子目录（如 `storage/index`），避免覆盖或删除应用的其他文件。
- **搜索分数阈值**: 当前使用 RRF (Reciprocal Rank Fusion) 融合，分数范围约 0.001–0.033。`RAG_SEARCH_SCORE_THRESHOLD_HYBRID/VECTOR` 必须设在 RRF 级别（默认 `0.003`），严禁用旧线性评分值（如 `0.25`）——会导致零结果。搜索页面同时启用 RRF → Per-Query Min-Max 归一化映射到前端显示分数。
- **DashScope Embedding 异常**: 遇 API 异常会返回 None 导致 Pydantic 报错，必须使用 `SafeDashScopeEmbedding` 包装器处理。

### 4. LLM 输出解析与文档上传
- **JSON 修复**: 请求 LLM 输出复杂 JSON 时，务必使用 `json-repair` 库作为后备，防止截断或格式错误。
- **列表字段校验**: 将 LLM 输出解析为 Pydantic 模型的 `List[str]` 时，若遇到单字符串需显式转换为数组 `[val]`。
- **文档上传排重**: 自动化任务（如测试用例生成）中，允许上传重复文档（返回已存在的文档引用），不要抛出 `ValueError`。
- **动态 Prompt 提取**: 生成测试草稿时，必须通过 `TEST_CASE_DRAFT_GENERATION_PROMPT` 动态提取，而不是硬编码 mock 数据。

### 5. 前端 SPA 路由
- **刷新 404 问题**: 前端使用 BrowserHistory，后端必须配置 SPA 回退路由，将非 API 路径的 404 请求返回 `index.html`。

### 6. 统一响应与异常处理
- **禁止 HTTPException**: 所有业务异常必须使用 `AppException` 或其子类，通过全局异常处理器统一格式化。
- **响应格式**: 成功响应必须使用 `APIResponse.success(data)` 包装，禁止直接返回字典。
- **实体类位置**: 发现 `class xxx(BaseModel)` 在 controller/service 中定义，必须迁移至 `schemas/` 目录。
- **类长度限制**: 单类超过 500 行必须拆分，使用门面模式协调子服务。
- **工具函数优先**: 遇到重复代码（Session 管理、文件操作、时间处理等），必须先检查 `utils/` 是否已有对应函数，禁止重复定义。

### 7. 配置与监控系统
- **配置热重载**: 通过 `ConfigCache` 单例 + Redis Pub/Sub 实现，修改配置后自动生效，无需重启。
- **Prometheus 指标**: 系统暴露 `/metrics` 端点，收集 HTTP 请求耗时、LLM 调用延迟、缓存命中率等。
- **Tracing 系统**: `core/tracing/` 实现全链路 Span 追踪，异步队列写入，支持耗时与成本分析。
  - **TraceWriter**: 异步队列写入器，支持批量写入和优雅关闭
  - **TraceContext**: 追踪上下文管理，支持 Span 嵌套和父子关系
  - **CostCalculator**: LLM 调用成本计算，支持多模型定价
- **中间件层**: `middleware/` 包含全局异常处理、响应包装、追踪中间件
  - **ExceptionHandler**: 统一异常处理，将业务异常转换为标准响应
  - **ResponseWrapper**: 自动包装成功响应为统一格式
  - **TraceMiddleware**: 自动注入 TRACE_ID，支持全链路追踪

### 8. Repository 数据访问层
- **泛型基类**: `BaseRepository` 提供 CRUD 通用实现，专属 Repository 继承并扩展。
- **Session 管理**: Repository 接收 `async_session_factory`，每个方法内部通过 `async with` 创建独立 session。
- **DI 注册**: 所有 Repository 通过 `RepositoryModule` 注册到 Injector 容器。

### 9. 前端测试与类型安全
- **测试框架**: Vitest 4.1 + React Testing Library 16.3，测试文件位于 `src/**/*.test.tsx`。
- **类型检查**: `npm run typecheck` 使用 TypeScript 严格模式，禁止 `any` 类型。
- **路由懒加载**: 提示词管理页面 (`/prompt-management/*`) 使用 `lazy()` + `Suspense` 按需加载；RAG 评估页面为 eager 加载。
- **状态管理**: 使用 Zustand 5 管理复杂业务状态
  - **RAG 评估状态**: `features/rag-eval/stores/` 包含草稿生成、测试运行、报告进度等状态
  - **状态持久化**: 支持状态持久化和恢复
- **API 客户端**: `api/` 目录按业务模块组织 API 客户端
  - **RAG 评估 API**: `api/rag-eval/` 包含草稿、测试用例、测试运行、报告等 API
  - **链路追踪 API**: `api/tracing.ts` 包含 Trace 和 Span 查询 API

---

# 🤖 协同开发核心纪律 (SDD + TDD)
> 详情与模板参见 `.ai/sdd_tdd_workflow.md`

在与我（AI助手）协同开发时，必须**严格且不可逆**地遵循以下流程：
1. **规范先行 (SDD)**：必须先有明确的机器可读规范（包含数据结构、接口契约、业务规则和验收标准）。
2. **测试生成 (TDD-Red)**：基于规范生成测试，并**必须确认测试全部失败**以建立验证基准。
3. **精准实现 (Coding-Green)**：只编写能让失败测试通过的最小代码集。
4. **循环推进**：严禁跳过测试直接生成业务代码！逻辑变更必须先更新规范（Spec）。
