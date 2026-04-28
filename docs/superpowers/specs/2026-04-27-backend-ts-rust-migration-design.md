# Backend TypeScript + Rust 迁移方案

> 将现有 Python (FastAPI + LangGraph + LlamaIndex) 后端迁移为 TypeScript (Node.js) + Rust (napi-rs) 架构，前端与后端技术栈统一。

---

## 1. 动机与目标

| 痛点 | 根因 | 目标 |
|------|------|------|
| 部署困难 | Python 运行时 + uv + 325 依赖 pip 安装，CI/CD 复杂 | `npm install && npm start` 一键启动 |
| 性能占用高 | Python GIL、动态类型运行时开销 | Rust 解决 CPU 密集型计算，TS 减少内存占用 |
| 前后端语言割裂 | 前端 TS、后端 Python，类型、工具、规范无法共享 | monorepo 下共享类型/校验/工具函数 |

**核心目标**：前后端统一 TypeScript，CPU 密集型模块下沉 Rust (napi-rs)，单体进程部署。

---

## 2. 架构总览

```
┌─────────────────────────────────────────────────┐
│                  Monorepo (npm workspaces)        │
│                                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌────────┐ │
│  │ @app/frontend │  │ @app/backend  │  │@app/   │ │
│  │ React 19      │  │ Hono (Node)   │  │ shared │ │
│  │ Vite 6        │  │ langgraph.js  │  │  Zod   │ │
│  │ Ant Design 6  │  │ LangChain.js  │  │ Types  │ │
│  │ Zustand 5     │  │ Drizzle ORM   │  │Consts  │ │
│  └──────┬───────┘  └──────┬────────┘  └────────┘ │
│         │                  │                       │
│         │         ┌────────▼────────┐             │
│         │         │  Rust .node     │             │
│         │         │  (napi-rs)      │             │
│         │         │  · 文档解析      │             │
│         │         │  · 向量检索      │             │
│         │         │  · 校验引擎      │             │
│         │         │  · ML 推理      │             │
│         │         └─────────────────┘             │
└─────────────────────────────────────────────────┘
```

**关键原则**：
- TS 层做编排、I/O、业务逻辑、LLM 调用
- Rust 层做 CPU 密集型纯计算（文档解析、向量检索、校验、ML 推理）
- 通过 napi-rs 在进程内零序列化调用 Rust，无 IPC 开销
- 单 `npm start` 启动，Rust 预编译为 `.node` 二进制随包分发

---

## 3. 技术栈映射

### 3.1 基础设施层

| 关注点 | Python (旧) | TypeScript + Rust (新) | 理由 |
|--------|------------|----------------------|------|
| HTTP 框架 | FastAPI 0.135 | **Hono** | 轻量高速，TS 优先，原生支持 Zod 校验、SSE、中间件 |
| API 数据校验 | Pydantic | **Zod** | 前后端共享 schema，编译期类型推导 |
| ORM | SQLAlchemy | **Drizzle ORM** | TS 优先，SQL-like API，迁移文件即为 DDL 源 |
| DI 容器 | Injector | **tsyringe** | TS 原生装饰器 DI |
| 异步任务 | AsyncTaskManager | **BullMQ** (Redis) | 生产级任务队列，重试/延时/优先级 |
| Redis | redis-py + hiredis | **ioredis** | 最成熟的 Node.js Redis 客户端 |
| 日志 | loguru | **pino** | 最快的 Node.js 日志库 |
| 监控指标 | prometheus-client | **prom-client** | Node.js 原生 Prometheus 客户端 |
| SSE 推送 | FastAPI StreamingResponse | **Hono SSE + RxJS** | 原生支持，流式响应简洁 |
| 配置管理 | ConfigManager + MySQL | **@app/backend/config** | 保持 MySQL 主存储 + 热重载架构 |
| 缓存三级 | cachetools/Redis/Disk | **lru-cache**/ioredis/disk | npm 生态 |
| JSON 修复 | json-repair | **jsonrepair** (npm) | 等效 |
| PDF 生成 | weasyprint | **puppeteer** | 通过 Chrome 渲染，质量更高 |
| Markdown 渲染 | markdown | **marked** | 等效 |

### 3.2 AI/LLM 层

| 关注点 | Python (旧) | TypeScript + Rust (新) | 理由 |
|--------|------------|----------------------|------|
| Agent 编排 | LangGraph (Python) | **@langchain/langgraph** (JS) | 官方 JS 版，API 一致 |
| LLM 适配 | LangChain + LlamaIndex | **LangChain.js** | 统一 TS 生态，支持 OpenAI/Anthropic/DashScope/Ollama |
| LLM 工厂 | LLMServiceFactory | **LLMFactory** (TS) | 同样的多提供商路由逻辑 |
| Embedding | DashScope (LlamaIndex) | LangChain.js DashScope Embedding | 等效 |
| 提示词管理 | PromptManager (MySQL) | **PromptService** (TS + MySQL) | 保持现有架构 |
| Tracing | 自定义 Span | **OpenTelemetry JS** | 标准化，支持 Loki/Tempo |

### 3.3 CPU 密集计算层 (Rust via napi-rs)

| 关注点 | Python (旧) | Rust (新) | 理由 |
|--------|------------|----------|------|
| PDF 解析 | PyMuPDF/pypdf | **lopdf** | 原生 Rust，零依赖 |
| EPUB 解析 | ebooklib + BS4 | **epub** crate | 原生 Rust |
| 中文分词 | jieba | **jieba-rs** | 性能提升 10x+ |
| BM25 检索 | llama-index-retrievers-bm25 | **tantivy** | 业界最快的全文检索引擎 (Rust 生态) |
| 向量检索 | Chroma (HTTP client) | **Qdrant** SDK (Rust) | 原生 Rust gRPC 客户端 |
| CrossEncoder 重排序 | sentence-transformers | **ort** (ONNX Runtime) + fastembed-rs | 通过 ONNX 推理，去除 Python 依赖 |
| XGBoost 推理 | xgboost + shap | **ort** (ONNX Runtime) | 模型导出为 ONNX 格式 |
| 6层校验引擎 | Python 自定义 | **Rust 重写** | 规则引擎+LLM 调用编排，LLM 调用归 TS |
| 语义分块 | SemanticSplitterNodeParser | **Rust 自定义** | 基于 embedding 相似度的分块算法 |
| Bloom Filter | pybloom-live | **bloomfilter-rs** | 原生 Rust |

---

## 4. Monorepo 目录结构

```
child-development-assessment-agent/
├── package.json                    # workspace root
├── turbo.json                      # Turborepo 配置
├── tsconfig.base.json              # 共享 TS 配置
├── pnpm-workspace.yaml
│
├── packages/
│   ├── shared/                     # @app/shared
│   │   ├── src/
│   │   │   ├── schemas/            # Zod schemas (前后端共享)
│   │   │   │   ├── assessment.ts
│   │   │   │   ├── rag.ts
│   │   │   │   ├── config.ts
│   │   │   │   ├── test-case.ts
│   │   │   │   ├── prompt.ts
│   │   │   │   └── common.ts       # APIResponse<T>, PaginatedResult<T>
│   │   │   ├── types/              # TypeScript 类型 (无 Zod)
│   │   │   │   ├── agent.ts        # AgentState, NodeResult
│   │   │   │   ├── llm.ts          # Provider, ModelConfig
│   │   │   │   └── domain.ts       # TestDomain, AgeRange 等枚举
│   │   │   ├── constants/          # 共享常量
│   │   │   │   ├── api.ts          # API 路径、错误码
│   │   │   │   └── business.ts     # 业务常量
│   │   │   └── utils/              # 共享工具函数
│   │   │       ├── date.ts
│   │   │       └── transform.ts
│   │   ├── package.json
│   │   └── tsconfig.json
│   │
│   ├── backend/                    # @app/backend
│   │   ├── package.json
│   │   ├── tsconfig.json
│   │   ├── native/                 # Rust crate (napi-rs)
│   │   │   ├── Cargo.toml
│   │   │   ├── build.rs
│   │   │   └── src/
│   │   │       ├── lib.rs          # napi 入口
│   │   │       ├── retrieval/      # 检索引擎
│   │   │       │   ├── mod.rs
│   │   │       │   ├── bm25.rs     # tantivy BM25
│   │   │       │   ├── vector.rs   # Qdrant 客户端
│   │   │       │   ├── fusion.rs   # 结果融合
│   │   │       │   └── reranker.rs # CrossEncoder 重排序
│   │   │       ├── parsing/        # 文档解析
│   │   │       │   ├── mod.rs
│   │   │       │   ├── pdf.rs      # lopdf
│   │   │       │   ├── epub.rs     # epub crate
│   │   │       │   └── chunker.rs  # 语义分块
│   │   │       ├── validation/     # 6层校验引擎核心
│   │   │       │   ├── mod.rs
│   │   │       │   ├── rules.rs    # 规则引擎
│   │   │       │   ├── compare.rs  # 对比逻辑
│   │   │       │   └── metrics.rs  # 指标计算
│   │   │       ├── ml/             # ML 推理
│   │   │       │   ├── mod.rs
│   │   │       │   └── onnx.rs     # ONNX Runtime 推理
│   │   │       └── tokenizer/      # 中文分词
│   │   │           └── mod.rs      # jieba-rs
│   │   └── src/
│   │       ├── server.ts           # Hono 入口
│   │       ├── index.ts            # Rust addon 绑定 & 导出
│   │       ├── api/                # 路由层
│   │       │   ├── routes/
│   │       │   │   ├── assessment.ts
│   │       │   │   ├── knowledge.ts
│   │       │   │   ├── search.ts
│   │       │   │   ├── rag-eval.ts
│   │       │   │   ├── config.ts
│   │       │   │   ├── prompt.ts
│   │       │   │   ├── monitoring.ts
│   │       │   │   └── health.ts
│   │       │   └── middleware/
│   │       │       ├── auth.ts
│   │       │       ├── cors.ts
│   │       │       ├── response.ts    # 统一响应包装
│   │       │       ├── error.ts       # 全局异常处理
│   │       │       ├── tracing.ts     # OpenTelemetry
│   │       │       └── metrics.ts     # Prometheus
│   │       ├── agents/             # Agent 编排层
│   │       │   ├── graph.ts        # langgraph.js 图定义
│   │       │   ├── nodes/
│   │       │   │   ├── preprocessing.ts
│   │       │   │   ├── validation.ts
│   │       │   │   ├── assessment.ts
│   │       │   │   ├── retrieval.ts
│   │       │   │   ├── scoring.ts
│   │       │   │   └── reporting.ts
│   │       │   └── state.ts        # AgentState 类型
│   │       ├── services/           # 业务服务层
│   │       │   ├── rag/
│   │       │   │   ├── retrieval.service.ts
│   │       │   │   ├── ingestion.service.ts
│   │       │   │   └── index-manager.service.ts
│   │       │   ├── evaluation/
│   │       │   │   ├── test-runner.service.ts
│   │       │   │   ├── draft.service.ts
│   │       │   │   ├── snapshot.service.ts
│   │       │   │   ├── validation.orchestrator.ts
│   │       │   │   └── report.service.ts
│   │       │   ├── cache/
│   │       │   │   ├── cache.service.ts    # 三级缓存门面
│   │       │   │   ├── l1-memory.ts
│   │       │   │   ├── l2-redis.ts
│   │       │   │   └── l3-disk.ts
│   │       │   ├── config/
│   │       │   │   ├── config.service.ts   # 配置管理
│   │       │   │   ├── config-cache.ts     # 热重载缓存
│   │       │   │   └── config-validator.ts
│   │       │   ├── prompt/
│   │       │   │   ├── prompt.service.ts   # 提示词管理
│   │       │   │   └── prompt-sandbox.ts
│   │       │   ├── llm/
│   │       │   │   ├── llm-factory.ts      # LLM 工厂
│   │       │   │   ├── providers/          # 多提供商适配
│   │       │   │   │   ├── openai.ts
│   │       │   │   │   ├── anthropic.ts
│   │       │   │   │   ├── dashscope.ts
│   │       │   │   │   └── ollama.ts
│   │       │   │   └── tracing.ts
│   │       │   ├── monitoring/
│   │       │   │   ├── monitoring.service.ts
│   │       │   │   └── alert.service.ts
│   │       │   ├── security/
│   │       │   │   ├── prompt-guard.ts
│   │       │   │   └── content-audit.ts
│   │       │   └── ab-test/
│   │       │       └── ab-test.service.ts
│   │       ├── repository/         # 数据访问层
│   │       │   ├── base.repository.ts
│   │       │   ├── config.repository.ts
│   │       │   ├── prompt.repository.ts
│   │       │   ├── test-case.repository.ts
│   │       │   ├── document.repository.ts
│   │       │   └── monitoring.repository.ts
│   │       ├── db/
│   │       │   ├── schema/         # Drizzle schema 定义
│   │       │   │   ├── config.ts
│   │       │   │   ├── test-case.ts
│   │       │   │   ├── prompt.ts
│   │       │   │   ├── document.ts
│   │       │   │   ├── monitoring.ts
│   │       │   │   └── index.ts
│   │       │   ├── migrations/     # Drizzle Kit 生成的迁移
│   │       │   └── connection.ts   # MySQL 连接池
│   │       ├── config/             # 配置入口
│   │       │   └── env.ts          # .env 解析 (兜底)
│   │       ├── native-bindings/    # napi-rs 的 TS 类型声明
│   │       │   └── index.ts
│   │       └── utils/              # 后端工具函数
│   │           ├── json-repair.ts
│   │           ├── sse.ts
│   │           └── di.ts           # tsyringe 容器配置
│   │
│   └── frontend/                   # @app/frontend (现有代码迁移至此)
│       ├── package.json
│       ├── tsconfig.json
│       ├── vite.config.ts
│       └── src/
│           ├── pages/
│           ├── features/
│           ├── entities/
│           ├── shared/
│           └── app/
│
├── .ai/                            # AI 参考文档 (保留)
│   ├── architecture.md
│   ├── infrastructure.md
│   ├── business_logic_map.md
│   └── ...
│
└── docs/                           # 项目文档 (保留)
    └── superpowers/
        └── specs/
            └── 2026-04-27-backend-ts-rust-migration-design.md
```

---

## 5. 前后端统一方案

### 5.1 共享类型 (packages/shared)

```typescript
// packages/shared/src/schemas/common.ts
import { z } from 'zod'

// 统一响应格式
export const APIResponseSchema = <T extends z.ZodType>(dataSchema: T) =>
  z.object({
    code: z.number(),         // 0 = 成功
    message: z.string(),      // "success" | 错误描述
    data: dataSchema.optional(),
    error_code: z.string().optional(),
    details: z.any().optional(),
  })

// 分页结果
export const PaginatedSchema = <T extends z.ZodType>(itemSchema: T) =>
  z.object({
    items: z.array(itemSchema),
    total: z.number(),
    page: z.number(),
    page_size: z.number(),
  })

// 业务领域枚举 (前后端共用)
export enum TestDomain {
  SENSORY_INTEGRATION = 'sensory_integration',
  GROSS_MOTOR = 'gross_motor',
  FINE_MOTOR = 'fine_motor',
  LANGUAGE = 'language',
  COGNITIVE = 'cognitive',
  SOCIAL_EMOTIONAL = 'social_emotional',
}
```

### 5.2 数据流 (前后端类型安全全程)

```
前端 (React)                     后端 (Hono)                    数据库 (MySQL)
┌─────────────┐    Zod 校验    ┌──────────────┐   Zod 校验   ┌──────────┐
│ Form Data   │──────────────►│ POST /api/... │────────────►│  Insert  │
│ Zod.parse() │               │ Zod.parse()  │             │          │
└─────────────┘               └──────┬───────┘             └──────────┘
                                     │
                              ┌──────▼───────┐
                              │  Response    │───► 前端 APIResponseSchema 解析
                              │  .json()     │     useQuery<Type> 类型安全
                              └──────────────┘
```

**收益**：前端表单校验逻辑和后端 API 校验逻辑共享同一份 Zod Schema，保证两端校验一致。

### 5.3 API 调用 (TanStack Query 类型推导)

```typescript
// frontend/src/shared/api/assessment.ts
import { APIResponseSchema } from '@app/shared'
import { useQuery } from '@tanstack/react-query'

const AssessmentResultSchema = APIResponseSchema(AssessmentSchema)

type AssessmentResult = z.infer<typeof AssessmentResultSchema>

export function useAssessmentResult(id: string) {
  return useQuery({
    queryKey: ['assessment', id],
    queryFn: async () => {
      const res = await fetch(`/api/v1/assessment/${id}`)
      const json = await res.json()
      return AssessmentResultSchema.parse(json)  // 运行时校验
    },
  })
}
// useAssessmentResult 返回类型自动推导为 AssessmentResult
```

---

## 6. Rust 原生扩展设计

### 6.1 napi-rs 接口契约

```rust
// native/src/lib.rs
use napi::bindgen_prelude::*;
use napi_derive::napi;

// --- 文档解析 ---
#[napi(object)]
pub struct ParsedDocument {
    pub pages: Vec<String>,
    pub metadata: DocumentMetadata,
    pub chunks: Vec<TextChunk>,
}

#[napi]
pub fn parse_pdf(file_path: String) -> Result<ParsedDocument> { ... }

#[napi]
pub fn parse_epub(file_path: String) -> Result<ParsedDocument> { ... }

// --- BM25 全文检索 ---
#[napi(object)]
pub struct SearchResult {
    pub doc_id: String,
    pub score: f64,
    pub snippet: String,
}

#[napi]
pub fn bm25_search(query: String, top_k: u32) -> Result<Vec<SearchResult>> { ... }

// --- 语义分块 ---
#[napi]
pub fn semantic_chunk(text: String, max_chunk_size: u32) -> Result<Vec<TextChunk>> { ... }

// --- 6层校验引擎 ---
#[napi(object)]
pub struct ValidationReport {
    pub layer_results: Vec<LayerResult>,
    pub overall_score: f64,
    pub suggestions: Vec<String>,
}

#[napi]
pub fn run_validation_check(
    test_result: String,  // JSON string
    baseline: Option<String>,  // 历史基线 JSON string (nullable)
) -> Result<ValidationReport> { ... }

// --- ONNX ML 推理 ---
#[napi]
pub fn xgboost_predict(features: Vec<f64>, model_path: String) -> Result<f64> { ... }

// --- 中文分词 ---
#[napi]
pub fn jieba_tokenize(text: String) -> Result<Vec<String>> { ... }
```

### 6.2 构建流程

```bash
# 开发时
cd packages/backend/native
cargo build --release
# 产出: native.linux-x64-gnu.node / native.darwin-x64.node / native.win32-x64.node

# CI 编译多平台 (GitHub Actions)
# 使用 @napi-rs/cli 的 prebuild 功能
npx napi prebuild
# 产出到 packages/backend/npm/{platform}/
```

### 6.3 TS 侧调用

```typescript
// packages/backend/src/native-bindings/index.ts
// 运行时自动加载对应平台的 .node 文件
import native from '../../native/index.node'

export const { 
  parsePdf, parseEpub,
  bm25Search, semanticChunk,
  runValidationCheck,
  xgboostPredict, jiebaTokenize
} = native
```

---

## 7. 核心模块迁移映射

### 7.1 Agent 编排层 (langgraph.js)

| Python 文件 | TS 文件 | 说明 |
|------------|---------|------|
| `core/graph.py` | `agents/graph.ts` | 图定义，langgraph.js 提供 `StateGraph` |
| `core/nodes/preprocessing.py` | `agents/nodes/preprocessing.ts` | 上下文压缩 |
| `core/nodes/validation.py` | `agents/nodes/validation.ts` | 数据校验 |
| `core/nodes/assessment.py` | `agents/nodes/assessment.ts` | 发展评估 |
| `core/nodes/retrieval.py` | `agents/nodes/retrieval.ts` | 混合检索（调用 Rust） |
| `core/nodes/scoring.py` | `agents/nodes/scoring.ts` | AHP 评分 |
| `core/nodes/reporting.py` | `agents/nodes/reporting.ts` | 报告生成 |

### 7.2 RAG 检索层 (TS 编排 + Rust 计算)

| Python 文件 | 新位置 | 技术 |
|------------|--------|------|
| `service/retrieval/facade.py` | `services/rag/retrieval.service.ts` | TS 门面 |
| `service/retrieval/query_rewriter.ts` | `services/rag/retrieval.service.ts` | LLM 调用 (LangChain.js) |
| `service/retrieval/retriever_manager.ts` | `native::retrieval/bm25.rs` + `::vector.rs` | **Rust tantivy + Qdrant** |
| `service/retrieval/result_processor.ts` | `native::retrieval/fusion.rs` + `::reranker.rs` | **Rust 融合 + ONNX 重排序** |
| `core/hybrid_retrieval.py` | `native::retrieval/fusion.rs` | **Rust** |
| `core/reranker.py` | `native::retrieval/reranker.rs` | **Rust ONNX Runtime** |
| `core/query_router.py` | `services/rag/retrieval.service.ts` | TS 路由 |
| `core/age_filter.py` | `services/rag/retrieval.service.ts` | TS 逻辑 |
| `core/context_compressor.py` | `agents/nodes/preprocessing.ts` | TS |
| `service/retrieval_service.py` | 拆分至上述文件 | — |

### 7.3 文档导入层 (TS 编排 + Rust 解析)

| Python 文件 | 新位置 | 技术 |
|------------|--------|------|
| `service/document_ingestion/facade.py` | `services/rag/ingestion.service.ts` | TS 门面 |
| `service/document_ingestion/document_parser.ts` | `native::parsing/pdf.rs` + `::epub.rs` | **Rust** |
| `service/document_ingestion/chunking_indexing.ts` | `native::parsing/chunker.rs` | **Rust 语义分块** |
| `core/parsers.py` | `native::parsing/` | **Rust** |
| `core/metadata_processor.py` | `native::parsing/` | **Rust** |
| `core/embedding.py` | `services/llm/` | TS (LangChain.js Embedding) |
| `core/vector_store_factory.py` | `native::retrieval/vector.rs` | **Rust Qdrant SDK** |
| `service/index_manager_service.py` | `services/rag/index-manager.service.ts` | TS + Rust |

### 7.4 6层校验引擎 (TS 编排 + Rust 计算)

| Python 文件 | 新位置 | 技术 |
|------------|--------|------|
| `core/validation/orchestrator.py` | `services/evaluation/validation.orchestrator.ts` | TS 编排 |
| `core/validation/layers/*` | `native::validation/` | **Rust** (规则引擎、对比、指标) |
| `core/tuning/engine.py` | `services/evaluation/tuning.service.ts` | TS (LLM 调用生成建议) |

### 7.5 基础设施层 (纯 TS 重写)

| Python 文件 | TS 文件 | 说明 |
|------------|---------|------|
| `core/llm/factory.py` | `services/llm/llm-factory.ts` | TS + LangChain.js |
| `core/prompt/manager.py` | `services/prompt/prompt.service.ts` | TS + Drizzle |
| `core/config/manager.py` | `services/config/config.service.ts` | TS + Drizzle |
| `core/di_container.py` | `utils/di.ts` | tsyringe |
| `core/async_task_manager.py` | `services/task/` | BullMQ |
| `service/cache_service.py` | `services/cache/cache.service.ts` | TS |
| `service/monitoring_service.py` | `services/monitoring/monitoring.service.ts` | TS |
| `core/tracing/` | `api/middleware/tracing.ts` | OpenTelemetry |
| `repository/*` | `repository/` | TS + Drizzle |

---

## 8. 数据迁移

### 8.1 MySQL DDL

**保持不变**。现有 `.ai/full_init_script_mysql57.sql` 中的 18 张表结构无需变更。Drizzle ORM 通过 `drizzle-kit introspect` 自动生成 schema 定义。

### 8.2 向量存储

从 Chroma (本地文件) 迁移到 **Qdrant** (可选择本地模式或 Server 模式)：
- 本地开发：Qdrant 本地模式 (嵌入式，零配置)
- 生产环境：Qdrant Server (Docker 部署，gRPC 高性能)

迁移脚本 (Python 一次性执行)：
```python
# 将现有 Chroma 数据导出为 JSON → 通过 Qdrant HTTP API 批量导入
# 此为一次性操作，导入后 Chroma 废弃
```

### 8.3 ML 模型

XGBoost 模型导出为 ONNX 格式：
```python
# 一次性操作
import xgboost as xgb
model = xgb.Booster()
model.load_model('model.json')
model.save_model('model.onnx')  # ONNX 格式，Rust 通过 ort 读取
```

---

## 9. 迁移阶段 (共 4 阶段)

### Phase 1: 基础设施搭建 (预计 1 周)
- 初始化 monorepo (Turbo + npm workspaces)
- 搭建 `@app/shared` 包 (Zod schemas + types)
- 搭建 `@app/backend` 骨架 (Hono server + Drizzle + DI + middleware)
- `@app/frontend` 代码迁移至 monorepo，引用 `@app/shared`
- 配置 ESLint/Prettier/TypeScript 统一规则
- CI/CD: GitHub Actions 编译 Rust + 构建 TS

### Phase 2: 核心 Rust 模块 (预计 2 周)
- 搭建 napi-rs 项目骨架
- 实现文档解析 (PDF + EPUB)
- 实现 BM25 检索 (tantivy)
- 实现语义分块
- 实现中文分词 (jieba-rs)
- 实现 6层校验引擎 (规则层 + 对比层)
- 编写 Rust 单元测试
- 编译多平台 `.node` 产物

### Phase 3: 业务逻辑迁移 (预计 3 周)
- LLM 工厂 + 多提供商适配 (LangChain.js)
- 配置管理系统 (MySQL + 热重载)
- 提示词管理系统
- Agent 编排 (langgraph.js 6 节点)
- RAG 检索流水线 (TS 编排 + Rust 计算)
- 文档导入流水线
- 异步任务系统 (BullMQ + SSE)
- 三级缓存
- 监控 & Tracing (OpenTelemetry + Prometheus)
- AB 测试框架

### Phase 4: 测试验收 & 部署 (预计 1 周)
- 后端单元测试 (Vitest)
- 后端集成测试 (API 契约测试)
- Rust 集成测试 (向量检索准确率、解析质量)
- 前后端联调
- 性能基准测试 (对比 Python 版)
- Docker 镜像构建 & 部署脚本
- 清理旧 Python 代码

**总预估：~7 周**

---

## 10. 关键技术决策

### 10.1 为什么选 Hono 而不是 Express/Fastify？
- 原生 TypeScript，Schema 校验与 Zod 深度集成
- 内置 SSE、Streaming、文件上传支持
- 路由性能优于 Express (基于 RegExpRouter)
- 可运行在 Node.js、Deno、Bun、Cloudflare Workers
- 更轻量 (12KB)

### 10.2 为什么选 napi-rs 而不是 gRPC/WASM？
- **零 IPC 开销**：进程内调用，无序列化
- **单进程部署**：一键启动，无需 sidecar
- **性能最高**：Rust 直接编译为机器码，没有 WASM 沙箱限制
- **生态成熟**：napi-rs 是 Node.js 原生模块的工业标准 (SWC、Parcel 都基于它)

### 10.3 为什么选 tantivy 而不是继续用 Chroma？
- Chroma 是 Python 生态，Rust 调用需要 HTTP/进程管理
- tantivy 是原生 Rust，编译进 `.node`，零外部依赖
- tantivy 性能远超 Chroma 的 BM25 实现
- Qdrant 用于向量检索，tativy 用于全文检索，各司其职

### 10.4 为什么保留 MySQL 而不是换 PostgreSQL？
- 项目约束要求 MySQL 5.7
- Drizzle ORM 对 MySQL 支持完善
- 向前兼容，无需数据迁移

### 10.5 为什么选 Drizzle 而不是 Prisma？
- Drizzle 的 SQL-like API 更透明
- 无代码生成步骤，schema 定义即 TypeScript
- Drizzle Kit 支持从现有数据库 introspect
- 更轻量，冷启动更快

---

## 11. 风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| langgraph.js API 与 Python 版不完全一致 | 编排逻辑需调整 | Phase 1 即验证 langgraph.js 核心 API |
| DashScope Embedding 在 LangChain.js 中的行为差异 | 向量检索质量下降 | Phase 3 用测试集做 A/B 对比验证 |
| ONNX 模型推理精度与 Python XGBoost 不一致 | 评分模型结果偏移 | 用相同测试数据比对输出，设定容差阈值 |
| napi-rs 编译多平台二进制时的依赖问题 | CI 构建失败 | 使用 napi-rs 官方 GitHub Action，预构建 |
| Tantivy 中文分词 (jieba-rs) 效果不如 Python jieba | BM25 检索质量下降 | 用相同 Query 集合比对召回结果 |
| Rust 学习曲线导致生产力下降 | 开发周期延长 | Rust 仅限 CPU 密集模块，TS 做大部分业务逻辑 |

---

## 12. 待决事项 (执行前需确认)

1. **Qdrant 部署模式**：本地嵌入式还是独立 Server？建议开发用嵌入式，生产用 Server
2. **BullMQ 是否保留**：当前 Redis 已使用，BullMQ 依赖 Redis，无额外部署成本
3. **旧 Python 代码处理**：确认直接删除（零迁移原则），不保留兼容层
4. **XGBoost 模型转换**：需确认当前训练好的模型可导出为 ONNX 格式
5. **langgraph.js 版本锁定**：需验证 @langchain/langgraph 最新版 API 稳定性
