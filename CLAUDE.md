# ⚠️ 核心工作原则 (不可忽略)

【以第一性原理！从原始需求和问题本质出发，不从惯例或模板出发。
1. 不要假设我清楚自己想要什么。动机或目标不清晰时，停下来讨论。
2. 目标清晰但路径不是最短的，直接告诉我并建议更好的办法。
3. 遇到问题追根因，不打补丁。每个决策都要能回答"为什么"。
4. 输出说重点，砍掉一切不改变决策的信息。】

【文件位置锁定】
- `CLAUDE.md` 必须始终位于项目根目录下，禁止移动。
- 这是 AI 助手介入项目的**唯一全局规则与入口**。
- 任何系统级架构改动，必须同步更新 `.ai/` 目录下的相应子文件。

---

# 🤖 AI 上下文路由字典 (Context Map)

为了保持 AI 专注与避免幻觉，系统的所有底层架构、业务逻辑与配置细节已剥离至专属的 `.ai/` 目录。

**【强制要求】当执行特定领域任务时，你必须主动调用 `Read` 工具读取对应的领域文档：**

| 领域 / 任务 | 查阅哪个文件/目录？ | 包含哪些信息？ |
|-------------|----------------|----------------|
| **快速逻辑定位** | `.ai/business_logic_map.md` | 各大业务模块（Agent/RAG/基建/测试）的核心逻辑概述与具体代码文件入口。 |
| **Agent 业务编排** | `.ai/agents_workflow.md` | LangGraph 状态管理、NodePre 到 Node5 节点职责与输入输出 |
| **系统架构与设计** | `.ai/architecture.md` | 多层架构总览图、各微服务或子系统的模块交互关系、数据流向 |
| **基础设施与配置** | `.ai/infrastructure.md` | 数据库(MySQL/Redis)参数、DI注入规范、LLM模型工厂、提示词管理 |
| **数据库初始化**   | `.ai/full_init_script_mysql57.sql` | 完整的 MySQL 5.7 DDL 脚本，包含建库、18张业务建表语句（无外键约束，采用弱关联） |
| **RAG 知识库检索** | `.ai/rag_pipeline.md` | RAG 核心模块、双流水线解析、向量库(Chroma)检索策略、API端点 |
| **协同开发规范**   | `.ai/sdd_tdd_workflow.md`| SDD+TDD 工作流 SOP、红绿重构规则、用于生成的 Prompt 模板 |
| **SDD+TDD实践指南**| `.ai/sdd_tdd_practice_guide.md` | 深入解析 SDD+TDD 融合实践的核心概念、全流程落地标准及避坑指南 |
| **RAG 完整技术文档**| `docs/RAG_SYSTEM_COMPLETE_DOCUMENTATION.md` | RAG 系统完整的技术细节与 API 规范 |
| **RAG+LLM 重构计划**| `docs/superpowers/plans/rag-llm-refactoring/` | RAG 与 LLM 架构重构的详细实施方案、进度追踪与验收标准 |
| **RAG页面重构计划**| `docs/superpowers/plans/rag-evaluation-page-refactoring/` | RAG 评估页面的6层校验诊断、工作流及 SSE 推送的详细重构计划 |
| **统一响应与异常规范**| `docs/specs/unified-api-response-and-error-handling.md` | 实体类管理、类拆分、冗余消除、统一响应格式、异常处理、错误码规范 |
| **统一响应与异常重构计划**| `docs/superpowers/plans/unified-api-response-error-handling/` | 统一接口返回与异常处理的详细实施方案、进度追踪与验收标准 |

---

# 📌 项目宏观概览与技术栈

**儿童发展评估 Agent** 是一个基于 AI 的多智能体系统，根据儿童的发展画像评估其运动计划。该系统使用 **LangGraph** 进行编排，采用前后端完全解耦架构。核心能力包含 RAG 知识检索、6层校验诊断引擎、以及多提供商 LLM 热切换支持。

## 技术栈
- **语言**: Python 3.13, TypeScript 5.3
- **核心编排**: LangGraph 1.1.0, LangChain 1.2.11, LlamaIndex 0.14.16
- **大模型支持**: DashScope, OpenAI, Anthropic, DeepSeek, Ollama
- **后端基建**: FastAPI 0.135.1, SQLAlchemy 2.0 (MySQL 5.7), Redis 7.0, Chroma (本地向量库), SSE 推送
- **前端架构**: React 19.2.4, Vite 6.4, Ant Design 6.3.2, Zustand 5, React Router 7
- **包管理**: uv (后端), npm (前端)

## 常用开发命令
- **后端**: `cd backend && uv sync && uv run start` 或 `uv run python src/server.py`
- **前端**: `cd frontend && npm install && npm run dev`

---

# 🏗️ 核心架构与开发约束

1. **前后端解耦**: 项目架构要求前后端完全解耦，后端仅提供 API 服务（及 SPA 回退路由），不包含任何前端业务路由逻辑。
2. **配置管理规范**: 
   - **绝对禁止代码硬编码**。所有可配置参数定义在数据库或集中式配置中心。
   - 在多实例部署架构中，动态编辑（如提示词、配置）必须使用 MySQL 共享存储，**禁止直接写入本地 JSON 文件**。
   - 系统全局配置页面通过独立路由 `/system-config` 访问。
3. **依赖管理**: 后端依赖只允许在 `pyproject.toml` 中声明，使用 `uv add`。前端使用 `package.json`。
4. **代码风格**: Python 遵循 PEP 8，使用强类型注解；前端使用 TS 严格模式。**代码注释必须全中文**。
5. **实体类集中管理（强制）**: 
   - **绝对禁止**在 `service/`、`controller/`、`core/` 中定义 `class xxx(BaseModel)`。
   - 所有 Pydantic 实体类必须统一放置在 `backend/src/schemas/` 目录下，按业务模块组织（如 `schemas/assessment.py`、`schemas/rag.py`）。
   - 详见 `docs/specs/unified-api-response-and-error-handling.md` 第 2 章。
6. **类职责拆分（强制）**: 
   - 单类不超过 **500 行**（含空行和注释），违反则必须拆分。
   - 使用门面模式（Facade）对外提供统一 API，内部协调子服务。
   - 详见 `docs/specs/unified-api-response-and-error-handling.md` 第 3 章。
7. **冗余代码消除（强制）**: 
   - 禁止重复定义相同功能的函数，必须提取至 `utils/` 目录下的对应工具模块。
   - 高频重复模式：Session 管理、错误处理、模型序列化、文件操作、时间处理。
   - 详见 `docs/specs/unified-api-response-and-error-handling.md` 第 4 章。
8. **统一响应与异常（强制）**: 
   - 所有接口返回统一格式：`{code: 0, message: "success", data: {...}}`（成功）或 `{code, message, error_code, details}`（错误）。
   - 保持 HTTP 语义（200/4xx/5xx），业务错误码采用双字段：`code`（数字）+ `error_code`（字符串）。
   - 所有业务异常必须继承 `AppException`，禁止直接使用 `HTTPException`。
   - 详见 `docs/specs/unified-api-response-and-error-handling.md` 第 5-7 章。

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
- **搜索分数阈值**: 融合搜索使用的绝对分数偏低（最高往往 50% 左右），因此阈值（如 `RAG_SEARCH_SCORE_THRESHOLD_HYBRID`）需适当调低至 `0.25`，并在前端进行线性映射。
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
- **类长度限制**: 单类超过 200 行必须拆分，使用门面模式协调子服务。
- **工具函数优先**: 遇到重复代码（Session 管理、文件操作、时间处理等），必须先检查 `utils/` 是否已有对应函数，禁止重复定义。

---

# 🤖 协同开发核心纪律 (SDD + TDD)
> 详情与模板参见 `.ai/sdd_tdd_workflow.md`

在与我（AI助手）协同开发时，必须**严格且不可逆**地遵循以下流程：
1. **规范先行 (SDD)**：必须先有明确的机器可读规范（包含数据结构、接口契约、业务规则和验收标准）。
2. **测试生成 (TDD-Red)**：基于规范生成测试，并**必须确认测试全部失败**以建立验证基准。
3. **精准实现 (Coding-Green)**：只编写能让失败测试通过的最小代码集。
4. **循环推进**：严禁跳过测试直接生成业务代码！逻辑变更必须先更新规范（Spec）。
