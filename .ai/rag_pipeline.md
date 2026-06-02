# RAG 双流水线架构与检索机制

> **文档定位**：本文档专注 RAG 检索系统的技术细节、配置参数与 API 规范。系统架构关系请参阅 `.ai/architecture.md`。知识问答 Agent 的 LangGraph 工作流请参阅 `.ai/agents_workflow.md`。

本文档详细描述知识库检索系统的核心模块、双流水线设计以及相关的 API 端点。

## RAG 系统架构

RAG 系统是本项目知识库检索的核心，采用分层架构，包含文档导入和知识检索两条流水线。同时，知识问答系统通过 **KnowledgeBundle** 把 RAG 检索与 Neo4j 知识图谱融合为三层优先级检索结果。

### 核心模块

**服务层（门面与业务逻辑）**

| 模块 | 文件路径 | 职责 |
|------|----------|------|
| RAG 门面服务 | `backend/src/service/rag_service.py` | 统一入口，聚合所有子服务 |
| 检索门面服务 | `backend/src/service/retrieval/facade.py` | 检索流水线入口，协调查询重写、检索、后处理 |
| 查询重写器 | `backend/src/service/retrieval/query_rewriter.py` | LLM 驱动的查询改写与扩展 |
| 结果处理器 | `backend/src/service/retrieval/result_processor.py` | 检索结果后处理、过滤、排序 |
| 知识检索器 | `backend/src/service/retrieval/knowledge_retriever.py` | 底层 BM25+向量检索执行（评估 Agent Node3 使用） |
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

**知识问答 Bundle 系统（v2 三层检索架构）**

| 模块 | 文件路径 | 职责 |
|------|----------|------|
| Bundle 数据模型 | `backend/src/core/knowledge_qa/bundle.py` | `KnowledgeBundle` 不可变知识产物，三层优先级: L0 自定义规则 > L1 Neo4j 图谱 > L2 原文证据 |
| Bundle 构建器 | `backend/src/core/knowledge_qa/bundle_builder.py` | Phase 1 编排: Neo4j 增强查询 → Chroma 批量搜索 → LazyGraphRAG 遍历 → 去重组装 |
| Bundle 消费器 | `backend/src/core/knowledge_qa/bundle_consumer.py` | Phase 2: 按节提取 passages + 构造 L0→L1→L2 优先级上下文注入 LLM |
| Bundle 配置 | `backend/src/core/knowledge_qa/bundle_config.py` | 全局开关、Phase 1/2/3 独立开关、流量比例灰度 |
| Neo4j 增强查询 | `backend/src/core/knowledge_qa/neo4j/enhanced_query.py` | Bundle Step 1a: S2 problems + custom_entities 作为种子，1-2 跳扩展实体和关系 |
| Neo4j Driver 管理 | `backend/src/core/knowledge_qa/neo4j/driver.py` | 同步/异步 Driver 单例，NEO4J_ENABLED 特性开关 |

**自定义知识系统**

| 模块 | 文件路径 | 职责 |
|------|----------|------|
| 自定义知识服务 | `backend/src/service/custom_knowledge_service.py` | 三通道匹配引擎(keyword→pattern→semantic) + 上传解析 + LLM 关键词生成 + 双写入库 |
| 自定义知识控制器 | `backend/src/controller/custom_knowledge_controller.py` | 上传 .md、列表查询、匹配测试、确认入库、CRUD |
| 自定义知识 Repository | `backend/src/repository/custom_knowledge_repository.py` | Neo4j CustomRule + MySQL 索引双存储 |
| 快速匹配节点 | `backend/src/core/knowledge_qa/nodes/fast_knowledge_match.py` | LangGraph 节点: 3 秒超时，命中后注入 L0 上下文 |

**D2G 文档→知识图谱流水线**

| 模块 | 文件路径 | 职责 |
|------|----------|------|
| D2G 书→图谱流水线 | `backend/src/core/knowledge_qa/d2g/book_pipeline.py` | 完整导入编排: 实体提取 → 图构建 → 社区检测 → 层级树存储 |
| D2G 书籍阅读器 | `backend/src/core/knowledge_qa/d2g/book_reader.py` | PDF/EPUB 文档解析 |
| D2G 章节提取器 | `backend/src/core/knowledge_qa/d2g/chapter_extractor.py` | 章节层级提取 |
| D2G 实体消歧器 | `backend/src/core/knowledge_qa/d2g/entity_resolver.py` | 跨书同义实体识别与合并 |
| D2G 全局关系推理 | `backend/src/core/knowledge_qa/d2g/global_relation_inference.py` | 跨书语义关系推断 |
| D2G 图谱写入器 | `backend/src/core/knowledge_qa/d2g/graph_committer.py` | 实体和关系写入 Neo4j |
| D2G 图谱质量检查 | `backend/src/core/knowledge_qa/d2g/graph_quality.py` | 图谱质量校验 |
| LazyGraphRAG 实体提取 | `backend/src/core/knowledge_qa/graph/extractor.py` | LLM 驱动的实体/关系提取 |
| LazyGraphRAG 图构建 | `backend/src/core/knowledge_qa/graph/builder.py` | NetworkX 图构建 + Louvain 社区检测 + 层级树 |
| LazyGraphRAG 遍历 | `backend/src/core/knowledge_qa/graph/traversal.py` | 层级树遍历 + LCA 查找 + 知识上下文构建 |
| 全局图谱重建 | `backend/src/core/knowledge_qa/graph/global_rebuild.py` | 跨书实体去重 + 全局社区检测 |

**RAG 评估服务层（RAG Eval Services）**

| 模块 | 文件路径 | 职责 |
|------|----------|------|
| 评估编排器 | `backend/src/service/rag_eval/orchestrator.py` | RAG 评估全流程编排 |
| 草稿引擎 | `backend/src/service/rag_eval/draft/` | 测试草稿生成、审核、去重 |
| 测试用例引擎 | `backend/src/service/rag_eval/case/` | 测试用例和测试集管理 |
| 测试运行引擎 | `backend/src/service/rag_eval/run/` | 批量测试执行、快照管理 |
| 指标引擎 | `backend/src/service/rag_eval/metrics/` | 评分和6层诊断 |
| 报告引擎 | `backend/src/service/rag_eval/report/` | 报告生成、趋势分析、导出 |
| 调优引擎 | `backend/src/service/rag_eval/tuning/` | 调优建议、冲突检测 |

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

---

## Neo4j 知识图谱 Schema

### 节点类型（27 种业务实体 + AutoEntity/CustomRule）

| 分类 | 节点类型 | 说明 |
|------|----------|------|
| **原有 8 种** | Book / Problem / RootCause / Solution / Exercise / Prescription / BrainRegion / ChildProfile / Risk / Chapter | 书籍、问题、根因、解决方案、运动、处方、脑区、儿童档案、风险 |
| **D2G 新增** | CognitiveProcess / Theory / Mechanism / DevelopmentalStage / Strategy / KeyInsight / ResearchFinding | 认知过程、理论、机制、发展阶段、策略、关键洞察、研究发现 |
| **D2G v2** | Person / Location / Object | 人名、地名、物品 |
| **D2G v3** | AssessmentTool / Symptom / Intervention / Diagnosis / Organization / Study / Neurotransmitter / Milestone / Environment | 评估工具、症状、干预、诊断、组织、研究、神经递质、里程碑、环境 |
| **扩展** | AutoEntity / AutoCommunity / CustomRule | 自动实体/社区回退类型、自定义知识规则 |

### 关系类型

| 分类 | 关系类型 |
|------|----------|
| **原有** | BELONGS_TO / CAUSES / SOLVES / PRESCRIBES / TARGETS / AFFECTS / REQUIRES / CONTAINS_ENTITY / RELATES_TO |
| **跨书消歧** | SAME_AS（同义实体边） |
| **跨书语义（22 种）** | CROSS_TREATS / CROSS_PREVENTS / CROSS_ALLEVIATES / CROSS_ADDRESSES / CROSS_IMPROVES / CROSS_ENHANCES / CROSS_CAUSES / CROSS_CONTRIBUTES_TO / CROSS_AFFECTS / CROSS_INCREASES_RISK / CROSS_OCCURS_AT / CROSS_SUPPORTED_BY / CROSS_EXPLAINED_BY / CROSS_SUPPORTS / CROSS_CONTRADICTS / CROSS_EXTENDS / CROSS_COMPLEMENTS / CROSS_ILLUMINATES / CROSS_LOCALIZED_IN / CROSS_INVOLVES / CROSS_EXPLAINS / CROSS_ASSOCIATED_WITH / CROSS_COMBINES_WITH |
| **自定义知识** | OVERRIDES（纠正/覆盖）/ ENHANCES（补充细节）/ SUPPLEMENTS（补充书籍） |
| **跨书聚合** | CROSS_BOOK_CONSENSUS / CROSS_BOOK_COMPLEMENTS / CROSS_BOOK_CONFLICTS |

---

## KnowledgeBundle 三层优先级模型

Bundle 是知识问答 v2 架构的核心——一次检索的完整不可变知识产物。

```
L0: 自定义规则（最高优先级，OVERRIDE/ENHANCES 指向 Neo4j 实体）
    ↓ 优先采纳，如有冲突以 L0 为准
L1: Neo4j 图谱权威数据（实体 + 关系 + 跨书冲突/共识）
    ↓ 实体验证过的原文 > 未验证原文
L2: Chroma 原文证据（Passage 带 source 标记）
    ↓ neo4j_verified=True 的 passage 优先
L1/L2: 冲突提醒（priority_conflicts 列表）
```

### Bundle 构建流程（Phase 1）

1. **Step 1a - Neo4j 增强查询**: S2 problems + custom_entities 作为种子，1-2 跳扩展获取实体、关系、跨书冲突/共识
2. **Step 1b - Chroma 批量搜索**: entity_seeds 并行搜索 + source_para_ids 直接召回，每个 query 返回 30 条
3. **Step 1c - LazyGraphRAG 增强遍历**: 社区树遍历补充知识上下文
4. **Step 1d - 组装**: 书籍剪枝 → 精确前缀去重 → SequenceMatcher 近似去重(≥0.90) → 截断(120 passages) → L1/L2 冲突检测

### Bundle 消费模式（Phase 2）

各节通过 `extract_for_section(bundle, section_index)` 提取 passages（按配额: S1=20%, S2=20%, S3=25%, S4=25%, S5=10%），然后 `build_priority_context()` 构造 L0→L1→L2 上下文注入 LLM prompt。

### 引用校验（Phase 3）

Bundle 模式下 `verify_citations_node` 执行五层校验:
- **L1**: excerpt/chapter 非空、citation_id 格式
- **L2**: book_title 白名单校验（必须在 bundle.book_index 中）
- **L3**: excerpt 溯源校验（必须在 bundle.passage_index 原文中找到匹配）
- **L4**: 图谱验证（excerpt 中的实体在 Neo4j 中存在）
- **L5**: 语义一致性校验（仅标记不剔除）

---

## 配置参数

### 关键阈值

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `RAG_SEARCH_SCORE_THRESHOLD_HYBRID` | 0.003 | RRF 融合分数阈值（严禁用旧线性值如 0.25） |
| `RAG_SEARCH_SCORE_THRESHOLD_VECTOR` | 0.003 | 纯向量分数阈值 |
| `BUNDLE_BOOK_MIN_ENTITY_HITS` | 3 | Bundle 书籍最少 Neo4j 实体命中 |
| `BUNDLE_BOOK_MIN_PASSAGE_HITS` | 5 | Bundle 书籍最少 Chroma passage 命中 |
| `MAX_PASSAGES_PER_BUNDLE` | 120 | Bundle 全文 passage 上限 |
| `CHROMA_RESULTS_PER_QUERY` | 30 | 每 query 的 Chroma 返回条数 |
| `MAX_QUERIES` | 5 | Bundle 最多搜索 query 数量 |
| `SEMANTIC_DEDUP_THRESHOLD` | 0.90 | SequenceMatcher 近似去重阈值 |
| `SEMANTIC_THRESHOLD` (自定义知识) | 0.80 | 自定义知识语义匹配 cosine 阈值 |

### 自动持久化参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| **自动持久化** | 启用 | Chroma 索引自动保存 |
| **持久化间隔** | 300秒 | 自动保存间隔 |
| **Embedding 模型** | text-embedding-v4 | DashScope Embedding 模型 |
| **最大文本长度** | 1536 | Embedding 输入截断 |
| **批处理大小** | 10 | Embedding 批处理 |

### PageIndex 参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| **PageIndex** | 启用状态 | 页面级索引增强 |
| **熔断/重试/降级** | 可配置 | PageIndex 容错机制 |

---

## API 端点

### RAG 知识库（路由前缀: `/rag`）

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
| `/rag/import-progress` | GET | SSE 端点，实时推送导入任务状态 |
| `/rag/layered-progress/{task_id}` | GET | SSE 端点，分层任务总体进度 |
| `/rag/graph/global-rebuild` | POST | 全局知识图谱重建 |

### 知识问答（路由前缀: `/api/v1/knowledge-qa`）

| 端点 | 方法 | 功能 |
|------|------|------|
| `/api/v1/knowledge-qa` | POST | 触发知识问答（返回 task_id） |
| `/api/v1/knowledge-qa/status/{task_id}` | GET | 查询任务状态 |
| `/api/v1/knowledge-qa/cancel/{task_id}` | POST | 取消任务 |
| `/api/v1/knowledge-qa/stream/{task_id}` | GET | SSE 进度流 |
| `/api/v1/knowledge-qa/download/{task_id}/markdown` | GET | 下载 Markdown 报告 |
| `/api/v1/knowledge-qa/download/{task_id}/pdf` | GET | 下载 PDF 报告 |
| `/api/v1/knowledge-qa/graph/rebuild-global` | POST | 手动触发全局图谱重建 |
| `/api/v1/knowledge-qa/history` | GET | 历史记录列表 |
| `/api/v1/knowledge-qa/history/{task_id}` | GET/DELETE | 历史记录详情/删除 |

### 自定义知识（路由前缀: `/api/v1/custom-knowledge`）

| 端点 | 方法 | 功能 |
|------|------|------|
| `/api/v1/custom-knowledge/upload` | POST | 上传 .md 文件（最多 5 份） |
| `/api/v1/custom-knowledge/confirm` | POST | 确认入库（双写 Neo4j + MySQL） |
| `/api/v1/custom-knowledge/` | GET | 列表查询 |
| `/api/v1/custom-knowledge/match` | POST | 匹配测试（调试用） |
| `/api/v1/custom-knowledge/{rule_id}` | GET/PUT/DELETE | 获取/更新/删除 |

### 监控与配置

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

### RAG 评估（路由前缀: `/api/v1/rag/eval`）

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

---

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
