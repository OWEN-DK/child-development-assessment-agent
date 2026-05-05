# RAG 双流水线架构与检索机制

> **文档定位**：本文档专注 RAG 检索系统的技术细节、配置参数与 API 规范。系统架构关系请参阅 `.ai/architecture.md`。

本文档详细描述知识库检索系统的核心模块、双流水线设计以及相关的 API 端点。

## RAG 系统架构

RAG 系统是本项目知识库检索的核心，采用分层架构，包含文档导入和知识检索两条流水线。

### 核心模块

**服务层（门面与业务逻辑）**

| 模块 | 文件路径 | 职责 |
|------|----------|------|
| RAG 门面服务 | `backend/src/service/rag_service.py` | 统一入口，聚合所有子服务 |
| 检索门面服务 | `backend/src/service/retrieval/facade.py` | 检索流水线入口，协调查询重写、检索、后处理 |
| 查询重写器 | `backend/src/service/retrieval/query_rewriter.py` | LLM 驱动的查询改写与扩展 |
| 结果处理器 | `backend/src/service/retrieval/result_processor.py` | 检索结果后处理、过滤、排序 |
| 知识检索器 | `backend/src/service/retrieval/knowledge_retriever.py` | 底层 BM25+向量检索执行 |
| 文档导入服务 | `backend/src/service/document_ingestion_service.py` | 文档解析→分块→元数据→索引，支持断点续传 |
| 文档解析器 | `backend/src/service/document_ingestion/document_parser.py` | PDF/EPUB 解析，支持三级降级 |
| 分块索引器 | `backend/src/service/document_ingestion/chunking_indexing.py` | 语义分块与索引入库 |
| 索引管理服务 | `backend/src/service/index_manager_service.py` | 向量索引生命周期管理，自动持久化 |

**流水线编排层（Pipeline Steps）**

| 模块 | 文件路径 | 职责 |
|------|----------|------|
| 流水线编排器 | `backend/src/core/pipeline/orchestrator.py` | YAML 驱动的声明式流水线编排 |
| 缓存检查 | `backend/src/core/pipeline/steps/cache_check.py` | 检索缓存命中检查 |
| 查询重写 | `backend/src/core/pipeline/steps/query_rewrite.py` | LLM 查询改写步骤 |
| 查询路由 | `backend/src/core/pipeline/steps/query_router.py` | 简单/复杂查询分类路由 |
| 同义词扩展 | `backend/src/core/pipeline/steps/synonym_expansion.py` | jieba 分词 + 同义词扩展 |
| 混合检索 | `backend/src/core/pipeline/steps/hybrid_retrieval.py` | BM25 + 向量混合检索 |
| 结果融合 | `backend/src/core/pipeline/steps/result_fusion.py` | RRF (Reciprocal Rank Fusion) 结果融合 |
| 重排序 | `backend/src/core/pipeline/steps/reranking.py` | Cross-Encoder 重排序 |
| 去重 | `backend/src/core/pipeline/steps/deduplication.py` | 结果去重去噪 |
| PageIndex 增强 | `backend/src/core/pipeline/steps/pageindex_enhancement.py` | PageIndex 元数据增强 |

**RAG 核心模块 (`core/rag/`)**

| 模块 | 文件路径 | 职责 |
|------|----------|------|
| 查询分析器 | `backend/src/core/rag/query_analyzer.py` | 中文查询类型分类 (SHORT/TERMINOLOGY/DESCRIPTIVE/COMPLEX) |
| 分数校准器 | `backend/src/core/rag/score_calibrator.py` | 检索分数校准 |
| 去重引擎 | `backend/src/core/rag/dedup_engine.py` | MinHash 去重 |
| 本地同义词扩展 | `backend/src/core/rag/local_synonym_expander.py` | jieba 本地同义词扩展 |
| 同义词校验器 | `backend/src/core/rag/synonym_validator.py` | 同义词质量校验 |
| 边界处理器 | `backend/src/core/rag/boundary_handler.py` | 章节边界处理 |
| 指标计算器 | `backend/src/core/rag/metrics_calculator.py` | RAG 检索指标计算 |
| 模型预热器 | `backend/src/core/rag/model_warmer.py` | Embedding 模型预热 |

**基础设施模块**

| 模块 | 文件路径 | 职责 |
|------|----------|------|
| 混合检索融合器 | `backend/src/core/hybrid_retrieval.py` | BM25 + 向量结果融合，RRF 算法 |
| 向量存储工厂 | `backend/src/core/vector_store_factory.py` | 向量存储抽象层，支持 Chroma/Pinecone/Milvus/Weaviate |
| Embedding 工厂 | `backend/src/core/llm/embedding_factory.py` | Embedding 模型工厂 |
| Reranker 工厂 | `backend/src/core/llm/reranker_factory.py` | 重排序模型工厂 |
| 上下文压缩器 | `backend/src/core/context_compressor.py` | 检索后上下文压缩，Token 预算控制 |
| 元数据提取 | `backend/src/core/metadata/metadata_extraction.py` | LLM 驱动的元数据提取 |
| 分块管理器 | `backend/src/core/metadata/splitter_manager.py` | 文档分块策略管理 |

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

所有 RAG 配置在 `backend/src/config/` 模块中定义（`__init__.py` 聚合 `modules/rag/` 子模块），支持环境变量覆盖。主要配置分类：

- **混合检索**: BM25/Vector 权重、合并模式、Top-K、动态权重
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
| `/rag/import-progress` | GET | SSE 端点，实时推送导入任务状态、日志及总进度 |
| `/rag/layered-progress/{task_id}` | GET | SSE 端点，获取所有分层任务（解析/分块/向量化/摘要）的总体进度 |

路由前缀: `/api/v1/monitoring`

| 端点 | 方法 | 功能 |
|------|------|------|
| `/api/v1/monitoring/statistics` | GET | 获取调用统计与告警 |
| `/api/v1/monitoring/trend` | GET | 获取趋势数据 |
| `/api/v1/monitoring/model-distribution` | GET | 获取模型分布 |
| `/api/v1/monitoring/scenarios` | GET | 获取场景统计 |
| `/api/v1/monitoring/ab-comparison` | GET | A/B 测试 variant 对比 |

路由前缀: `/api/v1/config`

| 端点 | 方法 | 功能 |
|------|------|------|
| `/api/v1/config/current` | GET | 获取当前生效配置 |
| `/api/v1/config/versions` | GET | 列出配置版本历史 |
| `/api/v1/config/save` | POST | 创建新配置版本 |
| `/api/v1/config/rollback` | POST | 回滚到指定版本 |
| `/api/v1/config/schema` | GET | 获取动态配置表单 Schema |

路由前缀: `/api/v1/prompts`

| 端点 | 方法 | 功能 |
|------|------|------|
| `/api/v1/prompts/{prompt_key}` | GET | 获取提示词(支持A/B测试参数) |
| `/api/v1/prompts/{prompt_key}/versions` | GET/POST | 列出/创建提示词版本 |
| `/api/v1/prompts/ab-tests` | GET/POST | 列出/创建 A/B 测试 |
| `/api/v1/prompts/ab-tests/{test_id}/toggle` | POST | 启用/禁用 A/B 测试 |

路由前缀: `/api/v1/rag/eval`

通过 `RagEvalControllerRegistry` 注册 7 个子控制器：

| 子控制器 | 端点前缀 | 功能 |
|----------|----------|------|
| `draft_controller` | `/source-documents/upload`, `/drafts/*` | 源文档上传、草稿生成/审核/批量操作、SSE 生成进度 |
| `case_controller` | `/test-cases/*`, `/test-sets/*` | 测试用例 CRUD + 批量/导入、测试集 CRUD + 用例关联 + 导出 |
| `run_controller` | `/runs/*` | 测试运行 CRUD + 批量执行 + 对比、单用例执行、SSE 进度 |
| `metric_controller` | `/runs/{id}/metrics`, `/diagnosis`, `/evaluate` | 指标查询、6层诊断、触发评估 |
| `report_controller` | `/reports/*`, `/trends` | 报告列表/生成/导出、趋势分析 |
| `tuning_controller` | `/runs/{id}/tuning`, `/tuning/{id}/adopt\|reject\|ignore`, `/config-versions/*` | 调优建议管理、配置版本回滚 |
| `snapshot_controller` | `/snapshots/*` | 快照创建/列表/恢复 |

## RAG流水线与回测测试集成
回测测试与RAG检索流水线深度集成，保证测试的一致性、可复现性和隔离性：

### 核心集成点
1. **快照绑定执行**
   - 测试执行前自动生成当前知识库的完整快照，测试过程中所有检索请求都基于该快照执行，不受测试期间知识库变更影响。
   - 支持手动指定历史快照执行测试，便于对比不同知识库版本的检索效果。

2. **流量隔离机制**
   - 测试流量通过独立的RAG流水线实例执行，与生产流量完全隔离，不会污染生产缓存、不会影响生产服务性能。
   - 测试执行过程中产生的所有临时数据都会在测试完成后自动清理。

3. **全链路指标采集**
   - 测试执行时自动采集RAG流水线全链路指标：查询重写耗时、同义词扩展耗时、检索耗时、重排序耗时、结果融合耗时、Token消耗、LLM调用耗时等。
   - 所有指标与测试结果关联存储，支持多版本对比和趋势分析。

4. **版本关联追踪**
   - 每次测试自动关联当前生效的配置版本、模型版本、提示词版本，支持多维度交叉对比分析。
   - 测试结果可追溯到具体的配置变更和代码提交，便于定位问题根因。

### 测试环境优化
- 测试模式下自动关闭缓存预热、自动持久化等后台任务，避免影响测试结果准确性。
- 支持批量测试的并发度配置，根据服务器资源自动调整并行执行数量，保证测试效率。
- 提供测试执行的断点续传功能，异常中断后可从中断位置继续执行，无需重新运行全部测试用例。