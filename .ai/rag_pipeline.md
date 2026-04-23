# RAG 双流水线架构与检索机制

> **文档定位**：本文档专注 RAG 检索系统的技术细节、配置参数与 API 规范。系统架构关系请参阅 `.ai/architecture.md`。

本文档详细描述知识库检索系统的核心模块、双流水线设计以及相关的 API 端点。

## RAG 系统架构

RAG 系统是本项目知识库检索的核心，采用分层架构，包含文档导入和知识检索两条流水线。完整技术文档见 [RAG_SYSTEM_COMPLETE_DOCUMENTATION.md](./docs/RAG_SYSTEM_COMPLETE_DOCUMENTATION.md)。

### 核心模块

| 模块 | 文件路径 | 职责 |
|------|----------|------|
| RAG 门面服务 | `backend/src/service/rag_service.py` | 统一入口，聚合所有子服务 |
| 检索服务 | `backend/src/service/retrieval_service.py` | YAML 驱动的声明式核心检索逻辑，含缓存/重写/同义词扩展 |
| 文档导入服务 | `backend/src/service/document_ingestion_service.py` | 文档解析→分块→元数据→索引，支持断点续传 |
| 索引管理服务 | `backend/src/service/index_manager_service.py` | 向量索引生命周期管理，自动持久化 |
| 混合检索融合器 | `backend/src/core/hybrid_retrieval.py` | BM25 + 向量结果融合，动态权重 |
| Cross-Encoder 重排序器 | `backend/src/core/reranker.py` | BAAI/bge-reranker-v2-m3 重排序 |
| 查询路由器 | `backend/src/core/query_router.py` | 简单/复杂查询分类 |
| 动态年龄过滤器 | `backend/src/core/age_filter.py` | 根据儿童发展阶段动态调整过滤 |
| 分层内容生成器 | `backend/src/core/layered_content_generator.py` | L0摘要/L1概览/L2详情三层生成 |
| 上下文压缩器 | `backend/src/core/context_compressor.py` | 检索后上下文压缩，Token预算控制 |
| PageIndex 包装器 | `backend/src/core/pageindex_wrapper.py` | 无向量推理式层级树索引检索，含熔断/重试/降级 |
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

路由前缀: `/rag/test`

| 端点 | 方法 | 功能 |
|------|------|------|
| `/rag/test/cases` | POST/GET | 创建/列出测试用例 |
| `/rag/test/cases/{case_id}` | GET/PUT/DELETE | 获取/更新/删除测试用例 |
| `/rag/test/cases/import/preview` | POST | 预览JSON导入的测试用例 |
| `/rag/test/cases/batch` | POST | 批量导入测试用例 |
| `/rag/test/cases/batch/delete` | POST | 批量删除测试用例 |
| `/rag/test/run` | POST | 运行所有测试用例 (支持并发) |
| `/rag/test/run/{case_id}` | POST | 运行单个测试用例 |
| `/rag/test/runs` | GET | 列出所有测试运行 |
| `/rag/test/runs/{run_id}` | GET | 获取单个测试运行 |
| `/rag/test/run/{run_id}/stream` | GET | SSE 进度推送 |
| `/rag/test/runs/batch/delete` | POST | 批量删除运行记录 |
| `/rag/test/compare` | GET | 比较两个测试运行 |
| `/rag/test/snapshots` | POST/GET | 创建/列出快照 |
| `/rag/test/snapshots/{snapshot_id}` | GET | 获取单个快照 |
| `/rag/test/snapshots/{snapshot_id}/restore` | POST | 恢复快照 |
| `/rag/test/compare-configs/{v1}/{v2}` | GET | 对比配置版本 |
| `/rag/test/documents/upload` | POST | 上传源文档（默认自动生成草稿） |
| `/rag/test/documents` | GET | 列出所有源文档 |
| `/rag/test/documents/{doc_id}` | GET/DELETE | 获取/删除源文档 |
| `/rag/test/documents/{doc_id}/generate-drafts` | POST | 手动生成测试用例草稿 |
| `/rag/test/drafts/generate/{task_id}/stream` | GET | SSE 推送生成草稿进度 |
| `/rag/test/drafts` | GET | 列出草稿 |
| `/rag/test/drafts/{draft_id}` | GET/PUT | 获取/更新草稿 |
| `/rag/test/drafts/{draft_id}/review` | POST | 审核草稿 |
| `/rag/test/drafts/import` | POST | 导入已审核草稿 |
| `/rag/test/drafts/batch/delete` | POST | 批量删除草稿 |
| `/rag/test/drafts/{draft_id}/delete` | POST | 删除单个草稿 |
| `/rag/test/sets` | POST/GET | 创建/列出测试集 |
| `/rag/test/sets/{set_id}` | GET/PUT/DELETE | 获取/更新/删除测试集 |
| `/rag/test/sets/{set_id}/cases` | POST/DELETE | 添加/移除测试用例 |
| `/rag/test/sets/{set_id}/export` | GET | 导出测试集为JSON |

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