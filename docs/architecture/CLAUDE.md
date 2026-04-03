# CLAUDE.md - 项目指南

## 项目概览
**儿童发展评估 Agent (Child Development Assessment Agent)** 是一个基于 AI 的系统，根据儿童的发展画像评估其运动计划。该系统使用 **LangGraph** 进行编排，采用 **ReAct** 架构，并集成了 **LangChain** 和 **LlamaIndex**。

- **目标**: 根据用户输入自动生成专业的评估报告。
- **架构**: 多 Agent 系统 (预处理 -> 校验 -> 评估 -> 检索 -> 评分 -> 报告)。
- **前端**: React + TypeScript (已初始化)。
- **后端**: FastAPI + LangGraph (已实现基础架构)。
- **包管理**: uv

## 技术栈
- **语言**: Python 3.13.12, TypeScript 5.9.3
- **编排**: LangGraph 1.1.0
- **LLM 框架**: LangChain 1.2.11
- **RAG**: LlamaIndex 0.14.16
- **API**: FastAPI 0.135.1
- **校验**: Pydantic 2.12.5, Zod 3.x
- **日志**: Loguru 0.7.3
- **前端**: React 19.2.4, Ant Design 6.3.2, ProComponents 2.8.10
- **样式**: SCSS Module (禁止直接写 CSS，必须分离样式文件)
- **状态管理**: Zustand (全局), TanStack Query (服务端)
- **路由**: React Router v6/v7
- **可视化**: Ant Design Charts
- **工具库**: Lodash-es, Day.js, Clsx
- **数据库**: Vector DB (Chroma/Faiss), Graph DB (Neo4j - 计划中)
- **工具**: uv 0.10.9

## 常用命令

### 后端 (Python - 使用 uv)
- **进入目录**: `cd backend`
- **初始化环境**: `uv sync`
- **激活环境**: `source .venv/bin/activate`
- **安装依赖**: `uv sync` (或 `uv add <package>`)
- **运行服务**: `uv run python src/server.py`
- **API 文档**: `http://localhost:8000/docs`
- **运行测试**: `uv run pytest`
- **格式化代码**: `uv run black .`
- **Lint 检查**: `uv run flake8 .`

### 前端 (React)
- **进入目录**: `cd frontend`
- **安装依赖**: `npm install --legacy-peer-deps`
- **开发服务器**: `npm run dev`
- **构建**: `npm run build`
- **Lint 检查**: `npm run lint`

## 项目结构 (当前)
```
/
├── backend/             # 后端项目根目录
│   ├── .venv/           # 虚拟环境
│   ├── src/             # Python 源代码
│   │   ├── config/      # 配置文件
│   │   ├── controller/  # API 控制器
│   │   ├── core/        # Agent 核心逻辑
│   │   ├── model/       # 数据模型
│   │   ├── service/     # 业务服务
│   │   ├── utils/       # 工具类
│   │   └── server.py    # 后端入口
│   ├── logs/            # 后端日志
│   ├── pyproject.toml   # 后端依赖配置
│   ├── uv.lock          # 依赖锁定文件
│   └── opencode.json    # Agent 配置
├── frontend/            # 前端项目根目录
│   ├── src/             # React 源代码
│   ├── public/          # 静态资源
│   ├── package.json     # 前端依赖配置
│   └── vite.config.ts   # 构建配置
├── book/                # 知识库源文件 (PDF/EPUB)
├── README.md            # 项目说明
├── AGENTS.md            # Agent 定义文档
├── CLAUDE.md            # 本文件
└── IMPLEMENTATION_PLAN.md # 详细系统设计方案
```

## 规划结构 (目标)
```
/
├── src/                 # 后端源代码 (FastAPI + LangGraph)
│   ├── api/             # API 路由与控制器 (Routers)
│   ├── core/            # 核心组件 (Security, Middleware, Events)
│   ├── domain/          # 业务领域模型 (Entities, Value Objects)
│   ├── services/        # 业务逻辑服务 (Service Layer)
│   ├── agents/          # LangGraph Agent 逻辑
│   ├── graph/           # 工作流编排 (Workflows)
│   ├── schemas/         # Pydantic 数据传输对象 (DTOs)
│   ├── db/              # 数据库访问 (Repositories, Models)
│   ├── utils/           # 通用工具
│   └── server.py        # 应用入口
├── frontend/            # React 应用 (规划中)
│   ├── public/          # 静态资源
│   └── src/             # 源代码
│       ├── assets/      # 图片、样式等资源
│       ├── components/  # 公共组件 (Atomic Design)
│       ├── config/      # 全局配置 (路由、主题等)
│       ├── hooks/       # 自定义 Hooks
│       ├── layouts/     # 页面布局
│       ├── pages/       # 页面视图
│       ├── services/    # API 请求服务
│       ├── store/       # 状态管理 (Zustand/Redux)
│       ├── types/       # TypeScript 类型定义
│       ├── utils/       # 工具函数
│       ├── App.tsx      # 根组件
│       └── main.tsx     # 入口文件
├── books/               # RAG 数据源
└── tests/               # 测试代码
```

## 代码规范
- **风格**: Python 遵循 PEP 8。
- **日志**: 使用 `src.utils.logger` 而不是 `print`。
- **类型提示**: 所有函数签名必须包含类型提示。
- **文档字符串**: 复杂函数使用 Google 风格的文档字符串。
- **错误处理**: 使用自定义异常。
- **状态**: 保持 `AgentState` 整洁。
- **导入**: 优先使用绝对导入。
- **提示词管理**: 所有LLM相关的提示词必须统一存放在 `src/core/prompts.py` 文件中，禁止在业务代码中硬编码提示词。
- **注释规范**: 所有代码注释必须使用中文，禁止使用英文注释，确保代码可读性和团队协作一致性。

## 核心概念
- **StandardizedInput**: 校验后的标准数据格式。
- **AgentState**: 通过 LangGraph 传递的全局状态对象。
- **MCP Server**: 用于检索结构化知识的模型上下文协议服务器。
- **AHP**: 用于基准评分逻辑的层次分析法 (Analytic Hierarchy Process)。

## RAG 系统架构

RAG 系统是本项目知识库检索的核心，采用分层架构，包含文档导入和知识检索两条流水线。完整技术文档见 [RAG_SYSTEM_COMPLETE_DOCUMENTATION.md](./RAG_SYSTEM_COMPLETE_DOCUMENTATION.md)。

### 核心模块

| 模块 | 文件路径 | 职责 |
|------|----------|------|
| RAG 门面服务 | `backend/src/service/rag_service.py` | 统一入口，聚合所有子服务 |
| 检索服务 | `backend/src/service/retrieval_service.py` | 核心检索逻辑，含缓存/重写/同义词扩展 |
| 文档导入服务 | `backend/src/service/document_ingestion_service.py` | 文档解析→分块→元数据→索引，支持断点续传 |
| 索引管理服务 | `backend/src/service/index_manager_service.py` | 向量索引生命周期管理，自动持久化 |
| 混合检索融合器 | `backend/src/core/hybrid_retrieval.py` | BM25 + 向量结果融合，动态权重 |
| Cross-Encoder 重排序器 | `backend/src/core/reranker.py` | BAAI/bge-reranker-v2-m3 重排序 |
| 查询路由器 | `backend/src/core/query_router.py` | 简单/复杂查询分类 |
| 动态年龄过滤器 | `backend/src/core/age_filter.py` | 根据儿童发展阶段动态调整过滤 |
| 分层内容生成器 | `backend/src/core/layered_content_generator.py` | L0摘要/L1概览/L2详情三层生成 |
| 上下文压缩器 | `backend/src/core/context_compressor.py` | 检索后上下文压缩，Token预算控制 |
| PageIndex 包装器 | `backend/src/core/pageindex_wrapper.py` | 外部知识图谱检索，含熔断/重试/降级 |
| 结果融合器 | `backend/src/core/result_fusion.py` | PageIndex 与混合检索结果融合 |
| 向量存储工厂 | `backend/src/core/vector_store_factory.py` | 向量存储抽象层，支持多种向量库 |
| Embedding 封装 | `backend/src/core/embedding.py` | DashScope Embedding 安全包装器 |
| 元数据处理器 | `backend/src/core/metadata_processor.py` | 分块策略与元数据提取 |
| 文档解析器 | `backend/src/core/parsers.py` | PDF/EPUB 解析，支持三级降级 |

### 技术栈

| 组件 | 技术选型 |
|------|----------|
| RAG 框架 | LlamaIndex |
| 向量存储 | Chroma (本地持久化) |
| Embedding | DashScope text-embedding-v4 |
| BM25 检索 | llama_index.retrievers.bm25 + jieba |
| 重排序 | Cross-Encoder (BAAI/bge-reranker-v2-m3) |
| PDF 解析 | PyMuPDF + Qwen-VL (扫描版) |
| EPUB 解析 | EbookLib + BeautifulSoup |
| 语义分块 | SemanticSplitterNodeParser |
| 本地摘要 | summa (TextRank) |

### 关键配置

所有 RAG 配置在 `backend/src/config/settings.py` 中定义，支持环境变量覆盖。主要配置分类：

- **混合检索**: BM25/Vector 权重、合并模式、TopK、动态权重
- **缓存**: 启用状态、最大容量 (1000)、TTL (3600秒)
- **分块**: chunk_size (1024/1536)、overlap (200)、语义分块参数
- **重排序**: 模型名称、initial_k (30)、final_k (5)
- **年龄过滤**: 严格程度、容忍范围、适配度权重
- **PageIndex**: 启用状态、熔断/重试/降级配置
- **自动持久化**: 启用状态、间隔 (300秒)
- **Embedding**: 模型名称、最大文本长度 (1536)、批处理大小 (10)

### API 端点

路由前缀: `/rag`

| 端点 | 方法 | 功能 |
|------|------|------|
| `/rag/upload` | POST | 上传 PDF/EPUB 并后台索引 |
| `/rag/tasks/{task_id}/cancel` | POST | 取消上传任务 |
| `/rag/tasks` | GET | 列出所有上传任务 |
| `/rag/tasks/{task_id}` | GET | 查询任务状态 |
| `/rag/status` | GET | RAG 服务状态 |
| `/rag/documents/{filename}` | DELETE | 删除文档 |
| `/rag/documents` | GET | 列出已索引文档 |
| `/rag/search` | GET | 搜索知识库内容 |
| `/rag/documents/{file_hash}/chunks` | GET | 获取文档分块列表 |
| `/rag/chunks/{chunk_id}` | GET | 获取分块详情 |
| `/rag/layered-progress/{task_id}` | GET | 分层内容生成进度 |

# Claude/Agent Rules

## Backend Development

- **Dependency Management**: All backend dependencies must be explicitly configured in `backend/pyproject.toml`. Do not rely on implicit dependencies or manual installation without updating the configuration file.
- **Configuration Management**: 
  - 所有可配置参数必须在 `backend/src/config/settings.py` 中定义，并支持通过 `.env.dev` 环境变量覆盖
  - 禁止在业务代码中硬编码任何配置值，必须从 settings 对象读取
  - 新增配置项时必须同时添加到 `.env.dev.example` 作为示例
- **代码规范**:
  - 所有配置相关的修改必须同步更新配置文件，不得直接在代码中写死数值
- **RAG 系统修改规范**:
  - 修改 RAG 相关逻辑后，必须同步更新 `docs/RAG_SYSTEM_COMPLETE_DOCUMENTATION.md` 文档
  - 新增的 RAG 模块必须在本文档的"RAG 系统架构"章节中注册
  - 配置变更必须更新配置表格，包括环境变量名、默认值、说明
