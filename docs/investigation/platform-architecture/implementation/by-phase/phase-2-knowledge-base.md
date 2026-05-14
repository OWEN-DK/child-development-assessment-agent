# Phase 2：知识库管理——阶段实施文档

> **上游依赖**：Phase 1（权限与多租户）——JWT 中间件注入 tenant_id/user_id/roles，Repository 基类已改造为自动注入 `tenant_id`。
> **下游被依赖**：Phase 3（管道引擎）——管道通过 `kb_id` 引用知识库；Phase 4（搜索 API）——搜索端点；Phase 7（RAG 评估改造）——知识库快照。
> **关联文档**：
> - [实施清单](../implementation-checklist.md) §Phase 2
> - [代码级实施计划](../implementation-plan-detail.md) §二 知识库管理
> - [知识库模块完整规范](../by-module/03-knowledge-base.md)
> - [核心目标文档](../../core-objectives.md)
> - [需求文档](../requirements/03-knowledge-base.md)
> **最后更新**：2026-05-14

---

## 1. 阶段目标

实现多知识库独立管理的完整生命周期——从创建、文档上传、解析、分块、向量化到索引维护，支持三种向量后端（Chroma/Elasticsearch/Milvus）的透明切换和迁移。

核心交付物：

| 子系统 | 目标 |
|--------|------|
| **向量存储适配器** | 抽象三种向量后端的 CRUD/搜索接口，通过工厂模式透明切换 |
| **ACL 过滤器** | 检索时根据用户角色构建后端特定的文档级 ACL 过滤条件 |
| **分块引擎** | 5 种策略（fixed/semantic/paragraph/heading/recursive），策略变更触发全量索引重建 |
| **Embedding 引擎** | 多模型通用化封装，支持批量/增量向量化，从 backend core/embedding.py 继承改造 |
| **BM25 独立索引** | 为 Chroma/Milvus 后端维护独立 BM25 关键词索引（ES 后端使用 ES 内置 BM25） |
| **文档解析** | 从 backend core/parsers.py 继承 PDF/TXT/EPUB 解析能力，移除业务配置引用 |
| **服务层** | KB CRUD、文档管理、索引重建、后端迁移 4 个子服务，门面模式协调 |
| **API 层** | 3 个控制器（KB/文档/重建），标准 REST + SSE 进度推送 |

---

## 2. 任务清单

> 每项任务对应 [implementation-plan-detail.md](../implementation-plan-detail.md) 中的具体类定义。勾选 `[ ]` 标记未完成，`[~]` 标记进行中，`[x]` 标记已完成。

### 2.1 向量存储适配器

| # | 文件 | 任务 | 关键类/函数 |
|---|------|------|------------|
| 2.1.1 | `core/knowledge_base/vector_store/base.py` | 实现 `VectorStoreAdapter` 抽象基类 | `VectorStoreAdapter(ABC)`, `CollectionInfo` dataclass, `create_collection()`, `delete_collection()`, `add_embeddings()`, `search()`, `delete_by_filter()`, `get_collection_info()`, `_collection_name()` |
| 2.1.2 | `core/knowledge_base/vector_store/chroma.py` | 实现 `ChromaAdapter` | `ChromaAdapter(VectorStoreAdapter)`, `_get_client()`, 强制注入 `hnsw:space=cosine`, 存储路径 `storage/chroma/{tenant_id}/` |
| 2.1.3 | `core/knowledge_base/vector_store/elasticsearch.py` | 实现 `ElasticsearchAdapter` | `ElasticsearchAdapter(VectorStoreAdapter)`, ES KNN 查询, filter clause 注入, index 命名 `rag_{tenant_id}_{kb_id}`（全小写）, 映射字段包含 `embedding (dense_vector)` + `content (text)` + `doc_acl (keyword)` |
| 2.1.4 | `core/knowledge_base/vector_store/milvus.py` | 实现 `MilvusAdapter` | `MilvusAdapter(VectorStoreAdapter)`, Schema 定义（chunk_id VARCHAR PK, embedding FLOAT_VECTOR, doc_acl ARRAY VARCHAR）, 索引创建 IVF_FLAT/HNSW, Collection 命名 `rag_{tenant_id}_{kb_id}`（全小写） |
| 2.1.5 | `core/knowledge_base/vector_store/factory.py` | 实现 `VectorStoreAdapterFactory` | `VectorStoreAdapterFactory`, `get_adapter(backend_type)`, 懒初始化 + 异常处理（ES/Milvus 未配置时抛 `ConfigurationError`） |

- [ ] 2.1.1 — VectorStoreAdapter 抽象基类
- [ ] 2.1.2 — ChromaAdapter
- [ ] 2.1.3 — ElasticsearchAdapter
- [ ] 2.1.4 — MilvusAdapter
- [ ] 2.1.5 — VectorStoreAdapterFactory

### 2.2 ACL 过滤器

| # | 文件 | 任务 | 关键类/函数 |
|---|------|------|------------|
| 2.2.1 | `core/knowledge_base/acl_filter.py` | 实现 ACLFilterBuilder 基类 + 3 个后端实现 | `ACLFilterBuilder(ABC).build_filter(user_roles)`, `ChromaACLFilterBuilder`（where `$or` 语法）, `ESACLFilterBuilder`（filter `terms` + `must_not`）, `MilvusACLFilterBuilder`（expr `array_contains_any`）, God Mode 统一返回空条件 |

- [ ] 2.2.1 — ACLFilterBuilder 基类 + Chroma/ES/Milvus 三实现

### 2.3 分块引擎

| # | 文件 | 任务 | 关键类/函数 |
|---|------|------|------------|
| 2.3.1 | `core/knowledge_base/chunking/strategies.py` | 实现 5 种分块策略 + `Chunk` dataclass + `BaseChunkingStrategy` 抽象基类 | `Chunk(content, token_count, metadata)`, `BaseChunkingStrategy(ABC).chunk()`, `FixedSizeChunking`, `SemanticChunking`, `ParagraphChunking`, `HeadingChunking`, `RecursiveChunking`, `_estimate_tokens()` |
| 2.3.2 | `core/knowledge_base/chunking/engine.py` | 实现 `ChunkingEngine` 门面 | `ChunkingEngine`, `chunk(text, strategy_config)`, `preview(text, strategy_config, limit)`, `_apply_constraints()` 应用 min/max chunk_size |

- [ ] 2.3.1 — 5 种分块策略实现
- [ ] 2.3.2 — ChunkingEngine 门面

### 2.4 Embedding 引擎

| # | 文件 | 任务 | 关键类/函数 |
|---|------|------|------------|
| 2.4.1 | `core/knowledge_base/embedding/engine.py` | 从 `backend/src/core/embedding.py` 继承改造，通用化多模型支持 | `EmbeddingEngine`, `embed_batch(texts, model_config)`, `embed_single(text)`, 继承 `SafeDashScopeEmbedding` 的安全处理逻辑（空文本替换、超长截断、3 次重试、非瞬时错误检测）, 扩展支持 OpenAI/Anthropic embedding 模型, 维度校验, 批量自动拆分（按 `batch_size` 参数） |
| 2.4.2 | `core/knowledge_base/embedding/` | 保留 `embedding_batch.py` 中的批量调度逻辑（如需大文档分页处理） | 从 `backend/src/core/embedding_batch.py` 继承 |

- [ ] 2.4.1 — EmbeddingEngine 多模型通用化
- [ ] 2.4.2 — 批量调度逻辑继承

### 2.5 BM25 独立索引

| # | 文件 | 任务 | 关键类/函数 |
|---|------|------|------------|
| 2.5.1 | `core/knowledge_base/bm25_index.py` | 实现 `BM25IndexManager` 独立索引管理器 | `BM25IndexManager`, `add_chunks(kb_id, tenant_id, chunks)`, `remove_chunks(kb_id, tenant_id, chunk_ids)`, `search(kb_id, tenant_id, query, top_k)`, `rebuild(kb_id, tenant_id, chunks)`, `delete_index(kb_id, tenant_id)`, `get_info(kb_id, tenant_id)`, 索引结构 `storage/bm25/{tenant_id}/{kb_id}/` (index.json + id_map.json + metadata.json) |

- [ ] 2.5.1 — BM25IndexManager

### 2.6 文档解析

| # | 文件 | 任务 | 关键类/函数 |
|---|------|------|------------|
| 2.6.1 | `core/knowledge_base/parser.py` | 从 `backend/src/core/parsers.py` 继承，移除业务配置引用 | `PDFParser` (PyMuPDF + 书签分割), `PDFVLParser` (Qwen-VL 多线程并行), `PDFParserV2` (三级降级 VLM→OCR→TEXT), `EPUBParser` (EbookLib + TOC 层级), `TXTParser` (chardet 编码检测), `get_parser(file_path)` 工厂函数, 移除 `from src.config.modules.models.llm import LLMSceneConfig`, 移除 `settings.llm_scene_configs` 等业务配置引用，改为通过构造函数注入 LLM 配置 |

- [ ] 2.6.1 — 文档解析器继承改造

### 2.7 数据模型

| # | 文件 | 任务 | 关键类/函数 |
|---|------|------|------------|
| 2.7.1 | `models/knowledge_base.py` | 实现 `KnowledgeBase` SQLAlchemy Model | 字段：id, tenant_id, name, description, vector_backend (Enum), chunk_strategy (JSON), embedding_config (JSON), visibility (Enum), visible_roles (JSON), owner_id, status (Enum), document_count, chunk_count, storage_size_bytes, created_at, updated_at |
| 2.7.2 | `models/kb_document.py` | 实现 `KbDocument` SQLAlchemy Model | 字段：id, kb_id, tenant_id, filename, file_type (Enum), file_size, page_count, md5_hash, parse_status (Enum), error_message, text_content (MEDIUMTEXT), metadata (JSON), access_level (Enum), doc_acl (JSON), owner_id, chunk_count, uploaded_at |
| 2.7.3 | `models/kb_chunk.py` | 实现 `KbChunk` SQLAlchemy Model | 字段：id, kb_id, doc_id, tenant_id, chunk_index, content (MEDIUMTEXT), token_count, metadata (JSON), vector_id |
| 2.7.4 | `models/kb_rebuild_task.py` | 实现 `KbRebuildTask` SQLAlchemy Model | 字段：id, kb_id, tenant_id, trigger (Enum), status (Enum), progress_pct (TINYINT), progress_message, started_at, completed_at, error_message |

- [ ] 2.7.1 — KnowledgeBase Model
- [ ] 2.7.2 — KbDocument Model
- [ ] 2.7.3 — KbChunk Model
- [ ] 2.7.4 — KbRebuildTask Model

### 2.8 Schemas

| # | 文件 | 任务 | 关键类 |
|---|------|------|--------|
| 2.8.1 | `schemas/knowledge/knowledge_base.py` | 知识库 Schema | `VectorBackend`, `KnowledgeBaseStatus`, `KnowledgeBaseVisibility`, `ChunkType`, `ChunkSeparator`, `SimilarityMetric`, `MultilingualMode` 枚举 + `ChunkStrategyReq`, `EmbeddingConfigReq`, `CreateKnowledgeBaseReq`, `UpdateKnowledgeBaseReq`, `UpdateChunkStrategyReq`, `UpdateEmbeddingConfigReq`, `MigrateBackendReq`, `KnowledgeBaseSummary`, `KnowledgeBaseDetail`, `RebuildTriggeredResponse`, `PipelineReference`, `KbDeletionConflict` |
| 2.8.2 | `schemas/knowledge/document.py` | 文档 Schema | `ParseStatus`, `DocAccessLevel` 枚举 + `UpdateDocAclReq`, `DocumentSummary`, `ChunkPreviewItem`, `DocumentDetail`, `BatchUploadResult` |
| 2.8.3 | `schemas/knowledge/chunk.py` | 分块 Schema | `ChunkPreview`, `ChunkRead`, `ChunkPreviewResult` |
| 2.8.4 | `schemas/knowledge/rebuild.py` | 重建 Schema | `RebuildTrigger`, `RebuildStatus` 枚举 + `RebuildTaskSummary`, `RebuildStatusResponse`, `RebuildProgressEvent` |
| 2.8.5 | `schemas/knowledge/migration.py` | 迁移 Schema | `MigrationRequest`, `MigrationStatus`, `MigrationEstimate` |

- [ ] 2.8.1 — 知识库 Schema
- [ ] 2.8.2 — 文档 Schema
- [ ] 2.8.3 — 分块 Schema
- [ ] 2.8.4 — 重建 Schema
- [ ] 2.8.5 — 迁移 Schema

### 2.9 Repository

| # | 文件 | 任务 | 关键类/函数 |
|---|------|------|------------|
| 2.9.1 | `repository/knowledge/kb_repo.py` | `KnowledgeBaseRepository` | 继承 `BaseRepository[KnowledgeBase]`, `count_by_tenant()`, `search()` 多条件筛选 + SQL LIKE 名称搜索, 自动注入 `tenant_id` |
| 2.9.2 | `repository/knowledge/document_repo.py` | `DocumentRepository` | 继承 `BaseRepository[KbDocument]`, `get_by_md5()` MD5 去重查询, `list_by_kb()` 多条件筛选 |
| 2.9.3 | `repository/knowledge/chunk_repo.py` | `ChunkRepository` | 继承 `BaseRepository[KbChunk]`, `batch_insert()`, `get_by_doc_id()` 预览用, `delete_by_doc_id()`, `count_by_kb()` |
| 2.9.4 | `repository/knowledge/rebuild_repo.py` | `RebuildTaskRepository` | 继承 `BaseRepository[KbRebuildTask]`, `get_latest_running()`, `get_recent()` |

- [ ] 2.9.1 — KnowledgeBaseRepository
- [ ] 2.9.2 — DocumentRepository
- [ ] 2.9.3 — ChunkRepository
- [ ] 2.9.4 — RebuildTaskRepository

### 2.10 服务层

| # | 文件 | 任务 | 关键类/函数 |
|---|------|------|------------|
| 2.10.1 | `service/knowledge/constants.py` | 字节级常量定义 | `MAX_FILE_SIZE_BYTES=50MB`, `MAX_BATCH_FILES=50`, `MAX_BATCH_SIZE_BYTES=200MB`, `PARSE_TIMEOUT_SECONDS=300`, `PARSE_RETRY_MAX=1`, `CHUNK_SIZE_MIN=128`, `CHUNK_SIZE_MAX=4096`, `REBUILD_SSE_HEARTBEAT_SECONDS=15`, `REBUILD_STALE_TIMEOUT_SECONDS=3600` |
| 2.10.2 | `service/knowledge/parser_service.py` | `DocumentParserService` | `parse(file_path, file_type)`, `extract_metadata(file_path, file_type)`, 超时 5 分钟 + 重试 1 次 + 文件损坏不重试 |
| 2.10.3 | `service/knowledge/kb_service.py` | `KnowledgeBaseService`（门面） | `create()`, `list()`, `get_detail()`, `update()`, `delete()`, `update_chunk_strategy()`, `update_embedding_config()`, `migrate_backend()`, `_check_pipeline_references()`, `_validate_kb_access()` |
| 2.10.4 | `service/knowledge/document_service.py` | `DocumentService` | `upload()` 批量上传 + MD5 去重, `_parse_async()` 异步解析流水线, `list_documents()`, `get_detail()` + 分块预览, `delete()` 级联删除, `reparse()`, `update_acl()`, `chunk_preview()` |
| 2.10.5 | `service/knowledge/rebuild_service.py` | `RebuildService` | `trigger_rebuild()`, `_execute_rebuild()` 核心重建流水线, `watch_progress()` SSE 生成器, `get_latest_task()`, `get_recent_tasks()`, 重建期间旧索引只读保证 |
| 2.10.6 | `service/knowledge/migration_service.py` | `MigrationService` | `estimate_time()`, `migrate()` 6 步流程: 创建新后端→读取旧向量→写入新后端→验证完整性→切换→清理旧数据, `_rollback()` 原子性回滚 |
| 2.10.7 | `service/knowledge/preview_service.py` | 分块预览服务 | `preview_chunks(doc_id, strategy_config)` 流式分块 + 返回前 10 块 |
| 2.10.8 | `service/knowledge/sse_publisher.py` | `SSEPublisher` | 单知识库多连接广播, `subscribe()`, `unsubscribe()`, `publish()`, 心跳 15s |

- [ ] 2.10.1 — 常量定义
- [ ] 2.10.2 — DocumentParserService
- [ ] 2.10.3 — KnowledgeBaseService
- [ ] 2.10.4 — DocumentService
- [ ] 2.10.5 — RebuildService
- [ ] 2.10.6 — MigrationService
- [ ] 2.10.7 — PreviewService
- [ ] 2.10.8 — SSEPublisher

### 2.11 控制器

| # | 路由 | 任务 | 端点 |
|---|------|------|------|
| 2.11.1 | `controller/knowledge/kb_controller.py` | 知识库 CRUD + 策略变更 | `POST /api/v1/knowledge-bases`, `GET /api/v1/knowledge-bases`, `GET /api/v1/knowledge-bases/{id}`, `PUT /api/v1/knowledge-bases/{id}`, `PUT /api/v1/knowledge-bases/{id}/chunk-strategy`, `PUT /api/v1/knowledge-bases/{id}/embedding-config`, `POST /api/v1/knowledge-bases/{id}/migrate-backend`, `DELETE /api/v1/knowledge-bases/{id}`, `GET /api/v1/knowledge-bases/{id}/chunk-preview` |
| 2.11.2 | `controller/knowledge/document_controller.py` | 文档管理 | `POST /api/v1/knowledge-bases/{id}/documents`, `GET /api/v1/knowledge-bases/{id}/documents`, `GET /api/v1/knowledge-bases/{id}/documents/{doc_id}`, `DELETE /api/v1/knowledge-bases/{id}/documents/{doc_id}`, `POST /api/v1/knowledge-bases/{id}/documents/{doc_id}/reparse`, `PUT /api/v1/knowledge-bases/{id}/documents/{doc_id}/acl` |
| 2.11.3 | `controller/knowledge/rebuild_controller.py` | 重建任务 SSE | `GET /api/v1/knowledge-bases/{id}/rebuild/status` (SSE) |

- [ ] 2.11.1 — kb_controller
- [ ] 2.11.2 — document_controller
- [ ] 2.11.3 — rebuild_controller

---

## 3. 关键实现细节

### 3.1 VectorStoreAdapter 抽象接口设计

**为什么需要这个抽象？**

当前 `backend/` 代码中向量存储直接绑定 LlamaIndex 的 Chroma `VectorStoreIndex`。平台化改造后需要：
1. **多后端切换**：Chrom（开发/小数据）、ES（生产/大数据/全文搜索）、Milvus（超大规模/高性能）
2. **统一检索接口**：管道引擎中的 `VectorSearchExecutor` 通过适配器调用 `.search()`，不关心实际后端
3. **ACL 过滤注入**：检索时必须注入文档级 ACL 过滤条件，各后端语法不同（Chroma where / ES filter / Milvus expr）

**接口方法解释：**

```python
class VectorStoreAdapter(ABC):
    backend_type: str  # "chroma" | "elasticsearch" | "milvus"

    async def create_collection(kb_id, tenant_id, dimension, metadata) -> None
    # 创建知识库对应的 Collection/Index
    # metadata 传递后端特定配置：Chroma hnsw:space=cosine, ES shards/replicas, Milvus index_type

    async def delete_collection(kb_id, tenant_id) -> None
    # 删除 Collection/Index（知识库删除时级联调用）

    async def add_embeddings(kb_id, tenant_id, chunk_ids, embeddings, metadatas, texts) -> list[str]
    # 批量添加向量，返回后端分配的 vector_id 列表
    # texts 参数：ES 需要存储文本用于内置 BM25 全文搜索

    async def search(kb_id, tenant_id, query_embedding, top_k, filter_condition) -> list[dict]
    # 向量检索，filter_condition 为 ACLFilterBuilder 构建的过滤条件
    # 返回 [{chunk_id, doc_id, content, score, metadata}, ...]

    async def delete_by_filter(kb_id, tenant_id, filter_condition) -> int
    # 按条件删除向量（如 {"doc_id": "doc_001"}），返回删除数量

    async def get_collection_info(kb_id, tenant_id) -> CollectionInfo
    # 获取 Collection 统计信息（文档数、维度、存储大小）

    def _collection_name(kb_id, tenant_id) -> str
    # 命名约定：Chroma 用 {tenant_id}_{kb_id}，ES/Milvus 用 rag_{tenant_id}_{kb_id}（全小写）
```

**各后端关键差异处理：**

| 关注点 | Chroma | Elasticsearch | Milvus |
|--------|--------|---------------|--------|
| 命名 | `{tenant_id}_{kb_id}` | `rag_{tenant_id}_{kb_id}` (全小写) | `rag_{tenant_id}_{kb_id}` (全小写) |
| 主键 | 自动 UUID | `chunk_id` (keyword) | `chunk_id` (VARCHAR, primary) |
| 向量字段 | 隐式 | `embedding` (dense_vector) | `embedding` (FLOAT_VECTOR) |
| ACL 字段 | metadata `doc_acl` 数组 | `doc_acl` (keyword) | `doc_acl` (ARRAY VARCHAR) |
| 距离度量 | 强制 `hnsw:space=cosine` | mapping `similarity: cosine` | index `metric_type: COSINE` |
| 全文搜索 | 无（需独立 BM25） | ES 内置 BM25 | 无（需独立 BM25） |
| 过滤语法 | Chroma `$or` where | ES `bool.filter` | Milvus `expr` 字符串 |

### 3.2 ACL 过滤器注入点

**注入时机**：检索请求到达 `PipelineCompiler` 执行 `VectorSearchExecutor` 时。

**注入流程**：

```
检索请求 → PipelineCompiler
  ├─ [1] 从请求上下文提取 user_roles（JWT 中间件注入）
  ├─ [2] 判断 God Mode：user_roles 为空 → 返回空过滤条件
  ├─ [3] 根据知识库 vector_backend 选择 ACLFilterBuilder 实现
  │     ├─ Chroma → ChromaACLFilterBuilder
  │     ├─ ES → ESACLFilterBuilder
  │     └─ Milvus → MilvusACLFilterBuilder
  ├─ [4] 调用 builder.build_filter(user_roles) → 后端特定 filter dict
  ├─ [5] 将 filter_condition 注入 VectorStoreAdapter.search(filter_condition=...)
  └─ [6] 后端执行搜索时自动应用 ACL 过滤
```

**三个 Builder 的核心逻辑：**

- **ChromaACLFilterBuilder**：用 `$or` 语法遍历 `user_roles` 构建 where 条件，空 ACL（inherit）的文档对所有人可见
- **ESACLFilterBuilder**：用 `terms` 匹配 + `must_not exists` 兜底 inherit 文档
- **MilvusACLFilterBuilder**：用 `array_contains_any` 或 `in` 表达式 + `is null` 兜底 inherit 文档
- **God Mode**：三个 Builder 均返回空 `{}`，不过滤

**说明**：ACL 过滤只在文档设置了 `access_level=restricted` 且配置了 `doc_acl` 时生效。`inherit` 的文档（空 ACL）对知识库可见范围内的所有角色可见。

### 3.3 分块策略选择逻辑

**ChunkingEngine 门面**：

```python
class ChunkingEngine:
    def __init__(self):
        self._strategies = {
            "fixed_size": FixedSizeChunking(),
            "semantic": SemanticChunking(),
            "paragraph": ParagraphChunking(),
            "heading": HeadingChunking(),
            "recursive": RecursiveChunking(),
        }

    async def chunk(text, strategy_config) -> list[Chunk]:
        strategy_type = strategy_config.get("type", "fixed_size")
        strategy = self._strategies[strategy_type]
        chunks = await strategy.chunk(text, strategy_config)
        return self._apply_constraints(chunks, config)  # min/max chunk_size
```

**5 种策略原理：**

| 策略 | 核心原理 | 关键参数 | 适用场景 |
|------|---------|---------|---------|
| `fixed_size` | 按 separator 分割 → 按 chunk_size 合并 → 计算 overlap | chunk_size, overlap, separator | 通用文档，结构不明显 |
| `semantic` | 计算相邻句子的 embedding 余弦相似度，在相似度低于 threshold 处切分 | similarity_threshold, embedding_model | 学术论文、技术文档，语义连贯性重要 |
| `paragraph` | 按正则分割段落，短段落合并到相邻块直到满足最小句子数 | paragraph_separator_regex, min_sentences_per_chunk | 法律文书、政策文件，段落边界明确 |
| `heading` | 识别 Markdown/HTML 标题层级（H1/H2/H3），以标题为分块边界，保留 heading_path | heading_levels, preserve_heading_path | 技术手册、API 文档，标题层级完整 |
| `recursive` | 按优先级列表递归尝试：双换行→单换行→句号→空格→字符 | separator_priority_list, min/max_chunk_size | 混合格式文档，无统一结构 |

**策略变更触发全量重建**：更新 `knowledge_bases.chunk_strategy` → 创建 `kb_rebuild_tasks`（trigger=chunk_change）→ 后台异步执行 `_execute_rebuild()`。

### 3.4 BM25 索引生命周期

**触发条件**：向量后端为 `chroma` 或 `milvus` 时必须维护独立 BM25 索引。后端为 `elasticsearch` 时不维护（ES 内置 BM25 全文搜索）。

**索引结构**：

```
storage/bm25/{tenant_id}/{kb_id}/
├── index.json       # BM25Okapi 序列化索引（rank_bm25 库）
├── id_map.json      # 内部 ID → chunk_id 映射
└── metadata.json    # 创建时间、文档数、k1=1.5, b=0.75
```

**增量更新策略：**

| 事件 | 操作 | 说明 |
|------|------|------|
| 文档上传解析完成 | `BM25IndexManager.add_chunks()` | 增量添加新分块到索引 |
| 文档删除 | `BM25IndexManager.remove_chunks()` | 按 chunk_ids 删除 |
| 文档重新解析 | `remove_chunks()` + `add_chunks()` | 先删旧分块，再加新分块 |
| 分块策略变更（全量重建） | `BM25IndexManager.rebuild()` | 全量重建索引 |
| Embedding 配置变更 | 不改动（BM25 与向量无关） | — |
| 后端迁移 Chroma→ES | `BM25IndexManager.delete_index()` | ES 后端不需要独立 BM25 |
| 后端迁移 ES→Chroma | `BM25IndexManager.rebuild()` | 从 kb_chunks 全量重建 |
| 知识库删除 | `BM25IndexManager.delete_index()` | 删除整个索引目录 |

**并发控制**：单知识库单写锁（asyncio.Lock），避免并发增量更新导致索引损坏。

**参数固定**：k1=1.5, b=0.75，不接受用户配置（BM25 标准参数，研究表明此组参数对多数语料最优）。

---

## 4. 测试策略

### 4.1 单元测试

| # | 测试对象 | 测试内容 | 验证点 |
|---|---------|---------|--------|
| UT-2.1 | `FixedSizeChunking` | 输入固定文本，chunk_size=512, overlap=10% | 分块长度在 [min, max] 范围，重叠区域宽度正确（前块的 overlap 部分与后块开头相同） |
| UT-2.2 | `SemanticChunking` | 输入有语义边界的文本（如两段不相关内容拼接） | 分块边界在语义断裂处，不在句子中间截断 |
| UT-2.3 | `ParagraphChunking` | 输入 10 段落文本（含短段落） | 按 `\n\n` 切分，< min_sentences 的短段落合并到相邻块 |
| UT-2.4 | `HeadingChunking` | 输入 Markdown 含 H1/H2/H3 标题的文档 | heading_path 保留完整路径（如 "第1章-1.2-1.2.3"），每个标题下内容独立成块 |
| UT-2.5 | `RecursiveChunking` | 输入混合格式文本 | 按 `["\n\n", "\n", ". ", " "]` 优先级逐级尝试，所有块满足 max_chunk_size |
| UT-2.6 | `EmbeddingEngine` | Mock Embedding API，批量 32/64/128 文本 | 请求正确按 batch_size 拆分、返回向量维度正确、空文本替换为 "empty" |
| UT-2.7 | `ChromaACLFilterBuilder` | 传入 ["admin","editor"] → 输出 Chroma where | `$or` 语法正确，含 `{"doc_acl": {"$size": 0}}` inherit 兜底 |
| UT-2.8 | `ESACLFilterBuilder` | 传入 ["admin","editor"] → 输出 ES filter | `terms` + `must_not exists` 语法正确 |
| UT-2.9 | `MilvusACLFilterBuilder` | 传入 ["admin","editor"] → 输出 Milvus expr | `in` 表达式语法正确，含 `is null or len(doc_acl) == 0` inherit 兜底 |
| UT-2.10 | God Mode（三个 Builder） | 传入 [] 空列表 | Chroma/ES/Milvus 三个 Builder 均返回空 `{}`（不过滤） |
| UT-2.11 | `BM25IndexManager` 增量更新 | add 3 个 chunk → search → remove 1 个 → search | 增删后搜索结果正确变化，索引文件持久化可恢复 |

### 4.2 集成测试

| # | 测试对象 | 测试内容 | 验证点 |
|---|---------|---------|--------|
| IT-2.1 | 创建知识库（Chroma） | POST → 验证 MySQL + Chroma Collection | MySQL 记录存在，Chroma Collection 存在且 metadata 含 `hnsw:space=cosine` |
| IT-2.2 | 上传 PDF 并解析 | POST PDF → 等待异步解析 → GET 详情 | parse_status=parsed, text_content 非空, metadata 含 author/page_count |
| IT-2.3 | MD5 去重 | 上传同一文件两次 | 第一次 created[] 含文档，第二次 duplicates[] 含引用 |
| IT-2.4 | 批量上传 50 文件 | POST 50 个混合格式文件 | 50 条全部解析成功，无丢块，分块数 > 0 |
| IT-2.5 | 分块+向量化一致性 | 上传文档 → 等待解析 → 验证 | kb_chunks 记录数 == 向量存储中条目数 |
| IT-2.6 | 分块策略变更重建 | PUT chunk-strategy → SSE 监听 → 等待完成 | KB 状态 ready, chunk_count 变化, 搜索可用 |
| IT-2.7 | Embedding 配置变更重建 | PUT embedding-config → 等待完成 | 新向量维度正确，搜索正常 |
| IT-2.8 | Chroma 后端搜索 | 上传文档 → 向量检索 | 返回相关分块，score ∈ [0,1]（cosine similarity） |
| IT-2.9 | ES 后端搜索 | 同上，ES 后端 | 返回相关分块，score 合理 |
| IT-2.10 | Milvus 后端搜索 | 同上，Milvus 后端 | 返回相关分块，score 合理 |
| IT-2.11 | Chroma→ES 迁移 | POST migrate → 等待完成 | ES 索引文档数 == kb_chunks 记录数，搜索正常 |
| IT-2.12 | 迁移失败回滚 | Mock ES 写入失败 → 触发迁移 | KB status 恢复 ready，旧 Chroma 数据完好无损 |
| IT-2.13 | 重建期间只读可用 | 触发重建 → 并发搜索 | 旧索引返回结果，无 500 错误 |
| IT-2.14 | 重建期间禁止修改 | 重建中 → POST 上传文档 | 返回 409 Conflict |
| IT-2.15 | 文档 ACL 过滤（Chroma） | 2 个文档：inherit + restricted to admin → editor 搜索 | 仅返回 inherit 文档 |
| IT-2.16 | ACL 三后端一致性 | 同一知识库、同一用户 → Chroma/ES/Milvus 搜索 | 三后端返回相同文档子集 |
| IT-2.17 | 删除被引用知识库 | DELETE → 检查管道引用 | 409 + details.pipelines 列出引用管道名 |
| IT-2.18 | 删除知识库（force） | DELETE?force=true | 级联删除：文档/分块/向量/BM25 全部清理 |
| IT-2.19 | 解析失败重试 | Mock 解析器抛异常 | 自动重试 1 次 → parse_status=error, error_message 非空 |
| IT-2.20 | 重新解析 | POST reparse | 文档重新解析 + 分块 + 向量化全流程成功 |
| IT-2.21 | SSE 进度推送 | 触发重建 → EventSource 连接 | 收到 progress（含 progress_pct）和 complete 事件 |
| IT-2.22 | 分块预览 | GET chunk-preview?doc_id=xxx | 返回前 10 块，每块含 content + char_count + token_estimate |
| IT-2.23 | 租户隔离 | 租户 A 上传文档 → 租户 B 搜索同名 KB | 租户 B 返回空结果 |

### 4.3 关键测试场景（≥ 8）

1. **TS-2.1 — 端到端完整链路**：创建 KB（Chroma）→ 上传 PDF → 等待解析 → 搜索验证 → 修改分块策略 → 重建完成 → 搜索验证新策略生效 → 删除 KB → 验证级联清理

2. **TS-2.2 — 多后端平等能力**：同一文档集分别导入 Chroma/ES/Milvus 三个 KB → 同一查询 → 验证三后端返回结果语义一致（top-10 重叠率 ≥ 80%）

3. **TS-2.3 — 批量上传极限**：50 个文件（PDF×10, TXT×10, Markdown×10, HTML×10, EPUB×10）同时上传 → 验证全部解析成功、无丢块、MD5 去重生效

4. **TS-2.4 — 大文档极限**：上传 50MB PDF（约 2000 页）→ 解析 ≤ 5 分钟 → 分块数 ≥ 10000 → 全部向量化成功 → 搜索响应 ≤ 2s

5. **TS-2.5 — 损坏文件容错**：批量上传含 2 个损坏 PDF + 1 个格式不匹配文件 + 5 个正常文件 → 坏文件标记 error + error_message，好文件正常解析

6. **TS-2.6 — 迁移幂等性**：Chroma→ES 迁移 → 完成后再次请求迁移到 ES → 400 "ALREADY_SAME_BACKEND"

7. **TS-2.7 — 迁移回滚原子性**：Chroma→ES 迁移 → Mock ES 写入中途失败 → 旧 Chroma 数据完好、KB status=error、task status=failed

8. **TS-2.8 — 并发重建互斥**：同时发起分块策略变更 + Embedding 配置变更 → 第一个成功创建重建任务，第二个 409 Conflict

9. **TS-2.9 — 重建期间搜索可用**：1200 文档 KB 重建中 → 连续 50 次搜索请求 → 全部成功返回，响应耗时 ≤ 重建前的 2 倍

10. **TS-2.10 — 权限一致性**：同一 KB（2 个文档：inherit + restricted to admin）→ admin 搜索返回 2 个文档，editor 搜索返回 1 个（仅 inherit）

11. **TS-2.11 — 大型迁移不丢数据**：10000 文档 Chroma→ES 迁移 → 迁移后 ES 索引文档数 == kb_chunks 记录数 → 随机抽样 100 篇搜索验证

12. **TS-2.12 — 分块预览即时性**：上传 2000 页文档 → 请求分块预览 → 3 秒内返回前 10 块

13. **TS-2.13 — SSE 断线重连**：SSE 连接 → 断开 5 秒 → 重连 → 推送当前进度而非从 0% 开始

14. **TS-2.14 — 知识库删除级联清理**：KB 含 500 文档+50000 分块 → 删除 → Chroma Collection 不存在、BM25 目录不存在、MySQL 中 kb_* 三表无残留

---

## 5. 验收检查点

### 5.1 向量存储适配器

- [ ] `VectorStoreAdapter` 抽象基类定义完整，6 个抽象方法签名与实现规范一致
- [ ] `ChromaAdapter.create_collection()` 强制注入 `hnsw:space=cosine`
- [ ] `ElasticsearchAdapter.create_collection()` 映射定义正确：embedding dense_vector + content text + doc_acl keyword
- [ ] `MilvusAdapter.create_collection()` Schema 定义正确：chunk_id VARCHAR PK + embedding FLOAT_VECTOR + doc_acl ARRAY
- [ ] 三种适配器的 `_collection_name()` 命名规则符合规范
- [ ] `VectorStoreAdapterFactory.get_adapter()` 能根据 backend_type 返回正确适配器，未配置时抛 `ConfigurationError`

### 5.2 ACL 过滤器

- [ ] `ACLFilterBuilder.build_filter()` 抽象方法定义完整
- [ ] `ChromaACLFilterBuilder` 输出 Chroma `$or` where 语法，含 inherit 文档兜底（`$size: 0`）
- [ ] `ESACLFilterBuilder` 输出 ES `terms` + `must_not exists` 语法
- [ ] `MilvusACLFilterBuilder` 输出 Milvus `expr` 字符串，含 inherit 文档兜底（`is null or len == 0`）
- [ ] God Mode（user_roles=[]）下三个 Builder 均返回空条件

### 5.3 分块引擎

- [ ] 5 种分块策略均继承 `BaseChunkingStrategy`，实现 `chunk(text, config)` 方法
- [ ] `ChunkingEngine.chunk()` 根据 `strategy_config.type` 正确选择策略
- [ ] `ChunkingEngine.preview()` 返回总分块数 + 前 N 块
- [ ] `_apply_constraints()` 确保所有块满足 `min_chunk_size` ≤ size ≤ `max_chunk_size`
- [ ] `_estimate_tokens()` 对中文（×1.5）和英文（×1.3）估算合理
- [ ] FixedSizeChunking 的 overlap 重叠区域文本与后块开头一致
- [ ] SemanticChunking 边界落在语义断裂处而非句子中间
- [ ] HeadingChunking 的 heading_path 完整保留层级路径
- [ ] RecursiveChunking 按 separator_priority_list 逐级尝试

### 5.4 Embedding 引擎

- [ ] 从 `backend/src/core/embedding.py` 继承 `SafeDashScopeEmbedding` 的安全处理逻辑
- [ ] 支持多模型（DashScope + OpenAI + Anthropic embedding 模型）
- [ ] `embed_batch()` 按 `batch_size` 自动拆分批量请求
- [ ] 空文本替换为 "empty" 占位符
- [ ] 超长文本截断至 `max_text_length`
- [ ] API 调用 3 次重试 + 指数退避 + 非瞬时错误检测（InvalidApiKey/401/403）
- [ ] 返回空 embedding 时抛 `ValueError`

### 5.5 BM25 索引

- [ ] `BM25IndexManager` 独立于向量后端，为 Chroma/Milvus 提供关键词检索
- [ ] 索引存储路径 `storage/bm25/{tenant_id}/{kb_id}/`，含 index.json + id_map.json + metadata.json
- [ ] `add_chunks()` 增量添加 + `remove_chunks()` 增量删除不影响已有索引
- [ ] `rebuild()` 全量重建覆盖旧索引
- [ ] `search()` 返回按 BM25 分数排序的 chunk 列表
- [ ] 单知识库单写锁（asyncio.Lock）防止并发损坏
- [ ] k1=1.5, b=0.75 固定参数
- [ ] ES 后端不创建独立 BM25 索引（使用 ES 内置 BM25）
- [ ] 后端迁移时正确处理索引的创建/删除

### 5.6 文档解析

- [ ] 从 `backend/src/core/parsers.py` 继承 PDFParser、PDFVLParser、PDFParserV2、EPUBParser、TXTParser
- [ ] 移除所有 `from src.config import settings` 业务配置引用，改为通过构造函数注入 LLM 配置
- [ ] 移除 `from src.config.modules.models.llm import LLMSceneConfig` 引用
- [ ] `get_parser(file_path)` 工厂函数支持 .pdf/.epub/.txt 扩展名
- [ ] PDFParserV2 三级降级（VLM→TEXT）正常工作
- [ ] 文件损坏时抛 `PDFCorruptedError`，不重试
- [ ] 解析超时 5 分钟后抛异常

### 5.7 数据模型 & Schemas

- [ ] 4 个 SQLAlchemy Model 字段与 DDL 完全一致
- [ ] Enum 字段使用 `values_callable=_enum_values` 防止大小写 LookupError
- [ ] `tenant_id` 冗余字段在 KbDocument、KbChunk 中正确设置
- [ ] 所有 Schema 在 `schemas/knowledge/` 下，通过 `__init__.py` 统一导出
- [ ] Pydantic `Config.from_attributes = True` 用于 ORM 序列化
- [ ] 枚举类与 Model 枚举值一致

### 5.8 服务层

- [ ] `KnowledgeBaseService.create()` 同时创建 MySQL 记录 + 向量存储 Collection + BM25 索引（如需）
- [ ] `KnowledgeBaseService.delete()` 级联删除：文档 → 分块 → 向量 → BM25 → 重建任务
- [ ] `KnowledgeBaseService.delete()` 检查管道引用，有引用时阻止并返回引用管道列表
- [ ] `DocumentService.upload()` MD5 去重逻辑：已存在返回 duplicates 引用而非报错
- [ ] `DocumentService._parse_async()` 完整流水线：解析→分块→向量化→索引更新
- [ ] `RebuildService._execute_rebuild()` 创建临时 Collection 保证重建期间旧索引只读
- [ ] `RebuildService._execute_rebuild()` 只处理 parse_status=parsed 的文档
- [ ] `MigrationService.migrate()` 6 步完整流程：创建→读取→写入→验证→切换→清理
- [ ] `MigrationService._rollback()` 失败时清理新后端 + 恢复 KB status ready
- [ ] `SSEPublisher` 支持单 KB 多连接广播 + 心跳 15s

### 5.9 控制器 & API

- [ ] 所有端点前缀 `/api/v1`，返回统一格式 `{code, message, data}`
- [ ] 认证头 `Authorization: Bearer <JWT>`（Phase 1 中间件注入 tenant_id/user_id/roles）
- [ ] `POST /knowledge-bases` 创建成功返回 201 + 完整配置
- [ ] `GET /knowledge-bases` 支持 search/vector_backend/status/visibility 筛选 + 分页
- [ ] `GET /knowledge-bases/{id}` 返回完整配置含 chunk_strategy 和 embedding_config
- [ ] `PUT /knowledge-bases/{id}/chunk-strategy` 返回 rebuild_task_id
- [ ] `PUT /knowledge-bases/{id}/embedding-config` 返回 rebuild_task_id
- [ ] `POST /knowledge-bases/{id}/migrate-backend` 返回 source/target backend + estimated_minutes + rebuild_task_id
- [ ] `DELETE /knowledge-bases/{id}` force=false 时检查引用，force=true 时跳过
- [ ] `POST /knowledge-bases/{id}/documents` multipart/form-data 支持批量 50 个文件
- [ ] `GET /knowledge-bases/{id}/documents/{doc_id}` 返回 chunk_preview 前 10 块
- [ ] `PUT /knowledge-bases/{id}/documents/{doc_id}/acl` 校验 doc_acl 不超出 visible_roles
- [ ] `GET /knowledge-bases/{id}/rebuild/status` SSE 推送 progress/complete/error 事件
- [ ] `GET /knowledge-bases/{id}/chunk-preview?doc_id=xxx` 返回前 10 块预览

### 5.10 非功能需求

- [ ] 单文档解析 ≤ 5 分钟（含 1 次重试）
- [ ] 批量上传 50 文件全部解析成功
- [ ] 重建期间搜索可用（读旧索引），响应耗时 ≤ 重建前 2x
- [ ] 后端迁移 10000 文档 ≤ 30 分钟（预估），迁移后数据完整
- [ ] 迁移失败原子回滚，旧数据完好
- [ ] 并发重建互斥（409 Conflict）
- [ ] SSE 心跳 15 秒 + 断线重连推送当前进度
- [ ] 知识库删除级联清理无残留
- [ ] 租户隔离：租户 A 文档对租户 B 不可见
- [ ] 所有 Repository 查询自动注入 `WHERE tenant_id = :tenant_id`

---

## 附录：文件清单

| 文件路径 | 类型 | 说明 |
|---------|------|------|
| `core/knowledge_base/vector_store/base.py` | 新建 | VectorStoreAdapter 抽象基类 + CollectionInfo |
| `core/knowledge_base/vector_store/chroma.py` | 新建 | ChromaAdapter |
| `core/knowledge_base/vector_store/elasticsearch.py` | 新建 | ElasticsearchAdapter |
| `core/knowledge_base/vector_store/milvus.py` | 新建 | MilvusAdapter |
| `core/knowledge_base/vector_store/factory.py` | 新建 | VectorStoreAdapterFactory |
| `core/knowledge_base/vector_store/__init__.py` | 新建 | 统一导出 |
| `core/knowledge_base/acl_filter.py` | 新建 | ACLFilterBuilder 基类 + 3 后端实现 |
| `core/knowledge_base/chunking/strategies.py` | 新建 | 5 种分块策略 + Chunk + BaseChunkingStrategy |
| `core/knowledge_base/chunking/engine.py` | 新建 | ChunkingEngine 门面 |
| `core/knowledge_base/chunking/__init__.py` | 新建 | 统一导出 |
| `core/knowledge_base/embedding/engine.py` | 继承改造 | EmbeddingEngine 多模型通用化 |
| `core/knowledge_base/embedding/__init__.py` | 新建 | 统一导出 |
| `core/knowledge_base/bm25_index.py` | 新建 | BM25IndexManager |
| `core/knowledge_base/parser.py` | 继承改造 | 文档解析器，移除业务配置 |
| `core/knowledge_base/__init__.py` | 新建 | 统一导出 |
| `models/knowledge_base.py` | 新建 | KnowledgeBase Model |
| `models/kb_document.py` | 新建 | KbDocument Model |
| `models/kb_chunk.py` | 新建 | KbChunk Model |
| `models/kb_rebuild_task.py` | 新建 | KbRebuildTask Model |
| `schemas/knowledge/__init__.py` | 新建 | 统一导出 |
| `schemas/knowledge/knowledge_base.py` | 新建 | 知识库请求/响应 Schema |
| `schemas/knowledge/document.py` | 新建 | 文档请求/响应 Schema |
| `schemas/knowledge/chunk.py` | 新建 | 分块响应 Schema |
| `schemas/knowledge/rebuild.py` | 新建 | 重建请求/响应 Schema |
| `schemas/knowledge/migration.py` | 新建 | 迁移请求/响应 Schema |
| `repository/knowledge/kb_repo.py` | 新建 | KnowledgeBaseRepository |
| `repository/knowledge/document_repo.py` | 新建 | DocumentRepository |
| `repository/knowledge/chunk_repo.py` | 新建 | ChunkRepository |
| `repository/knowledge/rebuild_repo.py` | 新建 | RebuildTaskRepository |
| `repository/knowledge/__init__.py` | 新建 | 统一导出 |
| `service/knowledge/constants.py` | 新建 | 字节级常量 |
| `service/knowledge/parser_service.py` | 新建 | DocumentParserService |
| `service/knowledge/kb_service.py` | 新建 | KnowledgeBaseService（门面） |
| `service/knowledge/document_service.py` | 新建 | DocumentService |
| `service/knowledge/rebuild_service.py` | 新建 | RebuildService |
| `service/knowledge/migration_service.py` | 新建 | MigrationService |
| `service/knowledge/preview_service.py` | 新建 | 分块预览服务 |
| `service/knowledge/sse_publisher.py` | 新建 | SSEPublisher |
| `service/knowledge/__init__.py` | 新建 | 统一导出 |
| `controller/knowledge/kb_controller.py` | 新建 | 知识库 CRUD + 策略变更 API |
| `controller/knowledge/document_controller.py` | 新建 | 文档管理 API |
| `controller/knowledge/rebuild_controller.py` | 新建 | 重建任务 SSE API |
| `controller/knowledge/__init__.py` | 新建 | 统一导出 |

**合计**：约 43 个文件（新建 36 + 继承改造 4 + 目录 `__init__.py` 若干）
