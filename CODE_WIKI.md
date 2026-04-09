# Child Development Assessment Agent - Code Wiki

## 1. 项目整体架构 (Overall Architecture)

本项目是一个基于 **LangGraph** 和 **FastAPI** 构建的儿童发展评估系统。它通过多 Agent 协作流程，结合先进的 RAG（检索增强生成）系统，对家长提供的儿童画像和拟定计划进行科学评估，并生成专业的改进建议。系统采用前后端分离架构。

### 1.1 核心评估工作流 (LangGraph Pipeline)
后端的评估核心是一个由专用 Agent/节点组成的有向循环图 (DAG)：
`预处理 (Preprocessing)` ➔ `校验 (Validation)` ➔ `评估 (Assessment)` ➔ `检索 (Retrieval)` ➔ `评分 (Scoring)` ➔ `报告生成 (Reporting)`

### 1.2 RAG 系统双流水线架构
- **文档导入流水线 (Ingestion)**：用户上传 PDF/EPUB ➔ 智能解析 (支持多模态 OCR) ➔ 语义分块 ➔ 智能元数据提取 ➔ 向量 Embedding ➔ Chroma 索引存储。
- **知识检索流水线 (Retrieval)**：用户查询 ➔ Query 路由 ➔ 缓存检查 ➔ 同义词扩展 ➔ 动态年龄过滤 ➔ 混合检索 (BM25 + Vector) ➔ Cross-Encoder 重排序 ➔ PageIndex 图谱增强 ➔ 结果融合返回。

---

## 2. 主要模块职责 (Main Module Responsibilities)

### 2.1 后端模块 (`backend/src/`)
- **`controller/` (API 路由控制)**: 负责接收 HTTP 请求，包含 `rag_controller` (处理文档上传和搜索), `task_controller` (评估任务), `rag_test_controller` (评测集接口)。
- **`core/` (Agent 与核心算法)**: 
  - `nodes/`: LangGraph 的各个工作流节点实现。
  - `parsers.py` / `metadata_processor.py`: 文档的解析与智能分块、元数据提取。
  - `hybrid_retrieval.py` / `reranker.py` / `query_router.py`: RAG 混合检索及核心策略。
  - `child_development_engine.py`: 负责基于《3-6 岁儿童学习与发展指南》计算年龄适配度和提取发展里程碑。
- **`service/` (业务服务层)**: 将 Core 的能力组合为具体业务，如 `RagService`, `DocumentIngestionService`, `RetrievalService`, `IndexManagerService` 等。
- **`model/` (数据模型)**: Pydantic 数据类 (Schemas)，定义了 API 交互结构和 Agent 状态内存 (`AgentState`)。
- **`config/`**: 项目环境变量、规则与 Prompt 统一配置。

### 2.2 前端模块 (`frontend/src/`)
- **`features/assessment/`**: 核心儿童发展评估功能，包含用户画像输入、计划表单填写及评估报告 (Markdown/雷达图) 渲染。
- **`features/documents/`**: 知识库管理，支持文档上传 (PDF/EPUB)、断点续传任务状态查询及文档删除。
- **`features/knowledge/`**: RAG 知识检索系统，支持自然语言检索和年龄过滤。
- **`features/rag-evaluation/`**: RAG 评测后台，支持展示评测集指标、Bad Case 列表与测试用例详情。
- **`pages/BookChunksPage.tsx`**: 文档分块详情查看，便于对切块质量进行 Debug。

---

## 3. 关键类与函数说明 (Key Classes & Functions)

### 3.1 LangGraph 核心节点类
- **`PreprocessingNode`**: 上下文窗口优化器，将大规模历史活动数据压缩为统计特征 (如周平均时长、频率一致性)。
- **`ValidationNode`**: 数据校验与标准化 Agent，利用 LLM (Qwen) 智能填补活动强度等缺失数据。
- **`AssessmentNode`**: 儿童发展评估模型，结合年龄里程碑评估前庭觉、本体觉等维度的强弱项状态。
- **`RetrievalNode`**: 混合检索专家，结合用户计划调用 `RagService` 获取科学依据。
- **`ScoringNode`**: AHP 多维评分 Agent，从科学性、年龄适配度、安全性三个维度对计划打分。
- **`ReportingNode`**: 综合汇总节点，通过 LLM 生成家长友好的流式/非流式 Markdown 报告。

### 3.2 RAG 核心组件
- **`DocumentIngestionService.ingest_book_resumable`**: 文档断点续传导入入口，串联解析、分块、元数据提取和持久化存储。
- **`RetrievalService.retrieve_knowledge`**: 知识检索全流程实现，内部调用 Query 路由、同义词扩展、混合召回与 Cross-Encoder 重排序。
- **`HybridRetrievalMerger.merge_results`**: 混合检索融合器，实现 BM25 与 Vector 的动态权重计算 (基于中文字符密度)、分数校准及归一化。
- **`PDFParserV2`**: 三级智能降级解析器，自动识别扫描版 PDF，通过 Qwen-VL 进行多模态 OCR 提取，保证文档解析质量。
- **`LayeredContentGenerator`**: 分层内容生成器，批量使用 LLM + TextRank 将文档内容转化为 L0(摘要)、L1(概览)、L2(详情) 的金字塔结构。

---

## 4. 依赖关系 (Dependencies)

### 4.1 后端技术栈 (Python 3.13)
- **Web 服务**: `fastapi`, `uvicorn`
- **AI 编排与检索**: `langgraph`, `langchain`, `llama-index`
- **向量数据库**: `llama-index-vector-stores-chroma` (主用), 支持 Pinecone/Milvus 扩展。
- **大模型支持**: `llama-index-llms-dashscope`, `llama-index-embeddings-dashscope` (通义千问 Qwen)。
- **算法与特征处理**: `sentence-transformers` (Cross-Encoder 重排), `jieba` (BM25 分词), `xgboost`, `shap`, `scikit-learn` (机器学习打分)。
- **文档解析**: `pypdf`, `pymupdf` (PDF), `ebooklib`, `beautifulsoup4` (EPUB), `html2text`。

### 4.2 前端技术栈 (Node)
- **核心框架**: `react` (v19), `react-dom`, `vite`, `typescript`
- **路由与状态**: `react-router-dom`, `zustand` (全局状态), `@tanstack/react-query` (服务端状态与缓存)。
- **UI 与展示**: `antd` (基础组件), `@ant-design/charts` (雷达图/统计图表), `sass`, `tailwindcss`。
- **工具库**: `dayjs`, `lodash-es`, `react-markdown` (报告渲染)。

---

## 5. 项目运行方式 (How to Run)

### 5.1 环境准备
- 确保系统安装有 Python 3.13+ 及 Node.js 环境。
- 推荐使用 `uv` 作为 Python 依赖包管理工具。

### 5.2 后端启动
```bash
# 1. 进入后端目录
cd backend

# 2. 安装依赖 (使用 uv 同步依赖)
uv sync

# 3. 准备配置文件 (如有需要，可基于 .env.dev.example 复制一份 .env.dev 并填入 DASHSCOPE_API_KEY)
cp .env.dev.example .env.dev

# 4. 启动服务
uv run python src/server.py
```
> 后端服务默认运行在 `http://0.0.0.0:8000`。可访问 `http://localhost:8000/docs` 查阅交互式 API 文档。

### 5.3 前端启动
```bash
# 1. 进入前端目录
cd frontend

# 2. 安装依赖
npm install

# 3. 启动开发服务器
npm run dev
```
> 前端服务启动后，通常运行在 `http://localhost:5173`。前端已配置 Vite Proxy 将 API 请求代理至 `http://127.0.0.1:8000`。
