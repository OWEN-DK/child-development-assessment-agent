# Phase 3：管道引擎（核心）

> **定位**：实现 PipelineCompiler（Python 主体 + Rust 热点，非 LangGraph，见 ADR-001）、NodeRegistry、28 节点执行器、管道 CRUD API、版本管理。5 个 CPU 密集型热点预留 Rust + PyO3 扩展点，一期全部 Python 实现。
> **前置阶段**：Phase 0（基础设施搭建）、Phase 1（权限与多租户）、Phase 2（知识库管理）
> **后置阶段**：Phase 4（搜索 API 与发布）
> **创建日期**：2026-05-14

---

## 1. 阶段目标

实现 RAG 平台的管道执行引擎，使租户可通过配置 JSON 定义"可组合的多域搜索管道"，系统自动编译为 DAG 并按拓扑顺序执行。

核心交付物：
- **PipelineCompiler**：将管道 JSON 配置编译为可执行的 `CompiledPipeline`，并驱动执行
- **NodeRegistry**：28 种节点的类型注册表，编译时按类型查找执行器
- **28 个节点执行器**：覆盖查询理解(7)、检索(5)、安全(3)、质量(4)、性能(2)、合成(1)、聚合(6) 全部类别
- **管道 CRUD**：管道的创建、读取、更新、删除、版本对比、回滚
- **复合节点**：可保存/导入/导出的节点组合单元

关键设计决策（来自 ADR-001/002）：
- **Python 主体 + Rust 热点**：编排框架和 23 个 I/O 密集型节点用 Python，5 个 CPU 密集型热点（MinHash/RRF/BM25/PII/分块）预留 Rust + PyO3 扩展点（见 [ADR-001](../../adr/001-pipeline-compiler-orchestration-backend.md)）
- **不依赖 LangGraph**：自实现 Kahn 拓扑排序 + `asyncio.gather` 并行
- **四层配置覆盖**：L3（API 参数） > L2（管道配置） > L1（租户覆盖） > L0（`NODE_DEFAULTS` 常量）
- **降级链式传递**：节点失败时按 `skip_node → reroute → degrade_cache → abort` 顺序尝试
- **渐进式 Rust**：一期全部用 Python 实现，Phase 8 后 profiling 验证再决定 Rust 重写范围

---

## 2. 任务清单

> 每项任务对应 `implementation-checklist.md` Phase 3 中的条目。
> 标记：`[ ]` 未开始，`[~]` 进行中，`[x]` 已完成

### 2.1 核心框架（3.1）

- [ ] `core/pipeline/node_context.py` — `NodeContext`：节点执行上下文，包含 input_data、config、tenant_id、user_id、user_roles、pipeline_id、pipeline_version、domain_id、node_id、node_type、trace_span、knowledge_base_id、degradation_registry
- [ ] `core/pipeline/node_result.py` — `NodeResult`：节点执行结果，包含 output、metadata、degraded、degradation_strategy、degradation_reason
- [ ] `core/pipeline/base_node.py` — `BaseNodeExecutor`：抽象基类，定义 `execute(context) → NodeResult`、`validate_config(config) → list[str]`、`get_input_type()`、`get_output_type()`
- [ ] `core/pipeline/registry.py` — `NodeRegistry`：单例注册表，`register(type, class)`、`get(type)`、`list_types()`、`create_executor(type)`
- [ ] `core/pipeline/compiled_pipeline.py` — `ExecutionPlan`（nodes, parallel_groups, conditional_routes, degradation_routes）、`PlanNode`（node_id, node_type, config, domain_id, knowledge_base_id, depends_on, downstream）、`CompiledPipeline`（config, execution_plan, domain_configs, aggregation_config）、`PipelineState`（query, params, auth_context, domain_plans, domain_results, merged_set, deduped_set, conflict_report, answer, shortcut_activated, degradation_events）、`AuthContext`（tenant_id, user_id, roles）
- [ ] `core/pipeline/exceptions.py` — `NodeNotRegisteredError`、`PipelineCompilationError`、`NodeExecutionError`、`DegradationChainExhaustedError`、`DomainTimeoutError`
- [ ] `core/pipeline/defaults.py` — `NODE_DEFAULTS` dict：所有 28 种节点类型的参数 L0 默认值（如 `top_k=10`、`similarity_metric=cosine`、`rrf_k=60`、`timeout_ms=3000`、`max_concurrency=5`、`temperature=0.3`、`include_citations=true` 等）
- [ ] `core/pipeline/degradation.py` — `DegradationRegistry`（按 node_id 注册降级策略，优先级：skip_node → reroute → degrade_cache → abort）、`NodeExecutorWrapper`（包装执行器，捕获异常后查降级注册表并执行策略：skip_node=上游输出直传、reroute=路由到备选节点、degrade_cache=取最近成功缓存、abort=抛出异常）

### 2.2 PipelineCompiler（3.2）

- [ ] `core/pipeline/compiler.py` — `PipelineCompiler` 类

**编译方法** `compile(pipeline_config: dict) → CompiledPipeline`：
1. `_validate_structure(config)`：校验 JSON 结构（必填字段：pipeline.id、pipeline.type、domains[]、aggregation）
2. `_validate_nodes(config)`：遍历所有域节点 + 聚合节点，调用各自的 `validate_config()`，收集错误
3. `_validate_edges(config)`：校验边合法性（源/目标节点存在、节点类型兼容性、域内边不跨域、无环检测）
4. `_build_execution_plan(config) → ExecutionPlan`：Kahn 拓扑排序 + 并行组识别 → 构建 `PlanNode[]` + `parallel_groups` + `conditional_routes` + `degradation_routes`
5. 返回 `CompiledPipeline`

**执行方法** `execute(compiled: CompiledPipeline, query: str, params: dict, auth_context: AuthContext) → PipelineResult`：
1. 初始化 `PipelineState`
2. `_execute_plan(plan, state)`：按拓扑顺序执行聚合层节点
3. 域分发节点通过 `asyncio.gather` 并行启动各域管道
4. 每个节点执行后调用 `_resolve_next_node()` 检查条件边
5. 节点失败时通过 `NodeExecutorWrapper` 触发降级

**内部方法**：
- `_build_graph(config) → dict[str, set[str]]`：从 edges 构建邻接表
- `_kahn_sort(adjacency, nodes) → list[str]`：Kahn 拓扑排序，返回顺序执行的节点 ID 列表，有环则抛出 `PipelineCompilationError`
- `_detect_parallel_groups(nodes, adjacency) → list[list[str]]`：识别无相互依赖的同层节点组
- `_resolve_next_node(current_node, state, plan) → str | None`：根据条件边决定下一跳，无匹配则返回 None（走默认数据流边）
- `_execute_parallel_domains(domain_plans, context, state) → list[DomainResult]`：`asyncio.gather` 并行执行域管道，受 `timeout_ms` 约束
- `_merge_params(params, config) → dict`：按 L3 > L2 > L1 > L0 优先级合并参数

### 2.3 查询理解节点（3.3，7 个）

**目录**：`core/pipeline/nodes/query/`（在 `core/pipeline/` 下组织，不在顶层 `nodes/`）

- [ ] `nodes/query/query_rewrite.py` — `QueryRewriteExecutor`：LLM 调用改写查询，输入 RawQuery，输出 `QueryVariant[]`。参数：`model`、`prompt_template`、`max_retries`(默认2)。改造提示词：根据上下文改写为检索优化的查询变体。
- [ ] `nodes/query/synonym_expand.py` — `SynonymExpandExecutor`：查同义词库扩展查询词。输入 `QueryVariant`，输出 `ExpandedQuery`。参数：`synonym_source`、`max_synonyms`(默认5)、`expansion_mode`(key_terms)。
- [ ] `nodes/query/query_decompose.py` — `QueryDecomposeExecutor`：LLM 调用拆解复杂查询为子查询。输入 `ComplexQuery`，输出 `SubQuery[]`。参数：`model`、`max_subqueries`(默认5)、`decomposition_strategy`(auto)。**改造自** `backend/src/core/query_decomposer.py`。
- [ ] `nodes/query/term_normalize.py` — `TermNormalizeExecutor`：查术语映射表替换非标准术语。输入 `RawQuery`，输出 `NormalizedQuery`。参数：`terminology_source`、`normalize_mode`(both)、`model`。
- [ ] `nodes/query/intent_classify.py` — `IntentClassifyExecutor`：LLM 调用分类查询意图。输入 `Query`，输出 `IntentLabel[]`。参数：`model`、`categories`、`routing_rules`。输出用于条件边 `intent_route` 路由。
- [ ] `nodes/query/stopword_filter.py` — `StopwordFilterExecutor`：正则/列表匹配移除禁用词。输入 `Query`，输出 `FilteredQuery`。参数：`stop_words`、`enabled`(默认false)、`case_sensitive`。
- [ ] `nodes/query/query_expand.py` — `QueryExpandExecutor`：LLM 调用生成扩展查询变体。输入 `Query`，输出 `QueryVariant[]`。参数：`model`、`expansion_count`(默认3)、`expansion_method`。

### 2.4 检索策略节点（3.4，5 个）

**目录**：`core/pipeline/nodes/retrieval/`

- [ ] `nodes/retrieval/bm25_search.py` — `BM25SearchExecutor`：BM25 检索。输入 `Query`，输出 `CandidateSet`。参数：`top_k`(默认10)、`k1`(默认1.5)、`b`(默认0.75)、`field_weights`(title/body)、`score_threshold`。ES 后端走 ES match，Chroma/Milvus 走独立 BM25 索引（`core/knowledge_base/bm25_index.py`）。**改造自** `backend/src/core/hybrid_retrieval.py` 的 BM25 部分。
- [ ] `nodes/retrieval/vector_search.py` — `VectorSearchExecutor`：向量检索。输入 `Query`，输出 `CandidateSet`。参数：`embedding_model`、`top_k`(默认10)、`similarity_threshold`、`similarity_metric`(cosine)、`collection_name`。调用 `VectorStoreAdapter.search()` + ACL 过滤。**改造自** `backend/src/core/vector_store_factory.py`。
- [ ] `nodes/retrieval/hybrid_search.py` — `HybridSearchExecutor`：BM25 + 向量并行检索 → RRF 融合。输入 `Query`，输出 `CandidateSet`。参数：`vector_weight`(默认0.6)、`keyword_weight`(默认0.4)、`top_k`、`fusion_method`(rrf)、`rrf_k`(默认60)。内部并行调 BM25 + vector_search → 融合。**改造自** `backend/src/core/hybrid_retrieval.py`。
- [ ] `nodes/retrieval/multimodal_search.py` — `MultimodalSearchExecutor`：文本/图片/表格多模态检索 → 融合。输入 `Query`，输出 `CandidateSet`。参数：各模态 `weight`(text/image/table)、各模态 `top_k`、`fusion_method`。**新建**。
- [ ] `nodes/retrieval/result_fusion.py` — `ResultFusionExecutor`：多分支 `CandidateSet` → RRF/加权融合。输入 `CandidateSet[]`，输出 `CandidateSet`。参数：`fusion_method`(rrf)、各分支 `weight`、`final_top_k`。**改造自** `backend/src/core/result_fusion.py`。

### 2.5 安全合规节点（3.5，3 个）

**目录**：`core/pipeline/nodes/security/`

- [ ] `nodes/security/sensitive_filter.py` — `SensitiveFilterExecutor`：敏感词过滤。输入 `CandidateSet`，输出 `CandidateSet`。参数：`word_list`(列表/导入/正则)、`filter_mode`(remove/mask/flag)、`apply_to`(query/results/both)。**新建**。
- [ ] `nodes/security/pii_mask.py` — `PIIMaskExecutor`：PII 脱敏（正则匹配手机号/身份证/邮箱/姓名/地址/银行卡号）。输入 `CandidateSet`，输出 `CandidateSet`。参数：`target_types`(多选)、`mask_char`(默认*)、`preserve_pattern`。**新建**。
- [ ] `nodes/security/content_audit.py` — `ContentAuditExecutor`：LLM/规则内容审核（色情/暴力/政治/违法/歧视/广告）。输入 `CandidateSet`，输出 `CandidateSet`。参数：`model`、`audit_rules`(多选)、`action`(filter/flag/reject)、`threshold`(默认0.7)。**改造自** `backend/src/service/content_audit_service.py`。

### 2.6 质量增强节点（3.6，4 个）

**目录**：`core/pipeline/nodes/quality/`

- [ ] `nodes/quality/rerank.py` — `RerankExecutor`：DashScope rerank API 或本地 cross-encoder 重排序。输入 `CandidateSet`，输出 `CandidateSet`。参数：`model`、`initial_k`(默认30)、`final_k`(默认5)。**改造自** `backend/src/core/reranker.py`。
- [ ] `nodes/quality/dedup.py` — `DedupExecutor`：MinHash 或 embedding 相似度去重。输入 `CandidateSet`，输出 `CandidateSet`。参数：`method`(minhash/embedding)、`threshold`(默认0.85)、`scope`(intra_domain/cross_doc/both)。一期 Python `datasketch` 库，预留 Rust MinHash + PyO3 扩展点（候选集 > 200 条时启用，5-10x 加速，见 ADR-001）。**新建**。
- [ ] `nodes/quality/hallucination_check.py` — `HallucinationCheckExecutor`：LLM 调用检测答案幻觉。输入 `CandidateSet`，输出 `CandidateSet`。参数：`model`、`threshold`(默认0.5)、`action`(filter/flag/both)。**新建**。
- [ ] `nodes/quality/citation_verify.py` — `CitationVerifyExecutor`：LLM 调用验证答案引用是否来自检索结果。输入 `CandidateSet`，输出 `CandidateSet`。参数：`mode`(strict/lax)、`model`。**新建**。

### 2.7 性能优化节点（3.7，2 个）

**目录**：`core/pipeline/nodes/performance/`

- [ ] `nodes/performance/semantic_cache.py` — `SemanticCacheExecutor`：Redis/内存语义缓存，命中返回缓存结果（输出 `CachedResult`），未命中输出 `None`（由条件边 `cache_miss` 路由到检索链）。参数：`cache_backend`(redis/memory)、`similarity_threshold`(默认0.95)、`ttl`(默认3600)、`cache_key_strategy`(exact/semantic)、`max_cache_size`、`cache_key_scope`(role_aware/role_agnostic)。缓存键构造：`hash(pipeline_id | query | [roles])`。**改造自** `backend/src/service/cache/`。
- [ ] `nodes/performance/rate_limiter.py` — `RateLimiterExecutor`：令牌桶/滑动窗口/漏桶算法限流。输入 `Query`，超限输出 `RateLimitError`。参数：`max_qps`、`algorithm`(token_bucket)、`scope`(per_domain/per_pipeline/per_user)、`action_on_limit`(queue/reject/degrade_cache)。**新建**。

### 2.8 答案合成节点（3.8，1 个）

**目录**：`core/pipeline/nodes/synthesis/`

- [ ] `nodes/synthesis/structured_output.py` — `StructuredOutputExecutor`：LLM 调用格式化为 JSON/Table/Markdown/自定义 Schema。输入 `CandidateSet`，输出 `StructuredResult`。参数：`output_format`(json)、`schema_definition`(JSON Schema)、`model`、`strict_mode`。使用 `json-repair` 库兜底 LLM 输出解析。**新建**。

### 2.9 聚合层节点（3.9，6 个）

**目录**：`core/pipeline/nodes/aggregation/`

- [ ] `nodes/aggregation/query_analyzer.py` — `QueryAnalyzerExecutor`：LLM 调用识别查询涉及的域，输出 `DomainPlan[]`。参数：`model`、`max_domains`(默认5)、`min_confidence`(默认0.6)、`domain_keywords`(各域触发关键词)。单域检测触发单域快捷路径（`state.shortcut_activated=true`）。**改造自** `backend/src/core/query_router.py`。
- [ ] `nodes/aggregation/domain_dispatch.py` — `DomainDispatchExecutor`：并行启动各域管道 + 权限裁剪（库级别可见性过滤）。输入 `DomainPlan[]`，输出 `DomainResult[]`。参数：`parallel`(默认true)、`timeout_ms`(默认3000)、`max_concurrency`(默认5)。权限裁剪：查知识库 `visibility` + `visible_roles`，用户角色无交集则跳过；超管不过滤。
- [ ] `nodes/aggregation/cross_fusion.py` — `CrossFusionExecutor`：多域结果 weighted RRF 融合。输入 `DomainResult[]`，输出 `MergedSet`。参数：`fusion_method`(weighted_rrf)、各域 `weight`、`rrf_k`(默认60)、`final_top_k`。**新建**。
- [ ] `nodes/aggregation/cross_dedup.py` — `CrossDedupExecutor`：MinHash/embedding 跨域去重。输入 `MergedSet`，输出 `DedupedSet`。参数：`dedup_threshold`(默认0.85)、`dedup_method`(minhash)。**新建**。
- [ ] `nodes/aggregation/conflict_detect.py` — `ConflictDetectExecutor`：LLM 调用检测跨域矛盾表述。输入 `DedupedSet`，输出 `ConflictReport`。参数：`model`、`enabled`(默认true)、`conflict_threshold`。**新建**。
- [ ] `nodes/aggregation/unified_generate.py` — `UnifiedGenerateExecutor`：LLM 调用综合多域结果生成最终答案。输入 `DedupedSet` + `ConflictReport`，输出 `Answer`。参数：`model`、`temperature`(默认0.3)、`max_tokens`、`include_citations`(默认true)、`citation_format`。**新建**。

### 2.10 节点注册（3.10）

- [ ] `core/pipeline/__init__.py` — 模块初始化时注册全部 28 种节点：
  - 查询理解(7)：`query_rewrite`, `synonym_expand`, `query_decompose`, `term_normalize`, `intent_classify`, `stopword_filter`, `query_expand`
  - 检索策略(5)：`bm25_search`, `vector_search`, `hybrid_search`, `multimodal_search`, `result_fusion`
  - 安全合规(3)：`sensitive_filter`, `pii_mask`, `content_audit`
  - 质量增强(4)：`rerank`, `dedup`, `hallucination_check`, `citation_verify`
  - 性能优化(2)：`semantic_cache`, `rate_limiter`
  - 答案合成(1)：`structured_output`
  - 聚合层(6)：`query_analyzer`, `domain_dispatch`, `cross_fusion`, `cross_dedup`, `conflict_detect`, `unified_generate`

### 2.11 数据模型（3.11）

- [ ] `models/pipeline.py` — `Pipeline`：id, tenant_id, name, description, type(aggregation), active_version, status(draft/active/error), created_at, updated_at
- [ ] `models/pipeline_version.py` — `PipelineVersion`：id, pipeline_id(FK), version_number(int, 同一管道自增), change_log, config_snapshot(LONGTEXT/JSON), created_at, created_by
- [ ] `models/compound_node.py` — `CompoundNode`：id, owner_id(user_id/或租户级), tenant_id, name, description, config_snapshot(LONGTEXT/JSON), is_shared(boolean), created_at, updated_at

### 2.12 Schemas（3.12）

**目录**：`schemas/pipeline/`（全部 Pydantic BaseModel，统一在 `__init__.py` 导出）

- [ ] `schemas/pipeline/pipeline.py` — `PipelineCreate`(name, description, type), `PipelineRead`(id, name, description, type, active_version, status, domain_count, created_at), `PipelineList`(items: list[PipelineRead], total), `PipelineUpdate`(name, description, status), `PipelineConfig`(pipeline 完整 JSON 配置结构)
- [ ] `schemas/pipeline/version.py` — `PipelineVersionRead`(id, pipeline_id, version_number, change_log, config_snapshot, created_at, created_by), `PipelineVersionListItem`(id, version_number, change_log, created_at), `VersionCompareResult`(v1, v2, added_nodes[], removed_nodes[], modified_nodes[], added_edges[], removed_edges[], param_changes[])
- [ ] `schemas/pipeline/node.py` — `NodeConfig`(id, type, config: dict, display: {x, y}), `NodeDefinition`(type, label, category, category_icon, icon, description, config_schema, default_config, input_ports[], output_ports[]), `NodeTypeList`(categories: [{name, icon, types: [NodeDefinition]}])
- [ ] `schemas/pipeline/edge.py` — `EdgeConfig`(id, source, target, type: data|conditional|degradation), `ConditionalEdgeConfig`(extends EdgeConfig with condition, condition_type: cache_hit|cache_miss|intent_route), `DegradationEdgeConfig`(extends EdgeConfig with strategy: skip_node|reroute|degrade_cache|abort, alternate_node_id)
- [ ] `schemas/pipeline/compound.py` — `CompoundNodeCreate`(name, description, expanded_nodes[], internal_edges[], exposed_ports: {input, output}), `CompoundNodeRead`(id, name, description, node_count, is_shared, created_at), `CompoundNodeImport`(json_string 或直接传 CompoundNodeCreate 结构)
- [ ] `schemas/pipeline/domain.py` — `DomainConfig`(id, name, knowledge_base_id, weight, activation_rules: {keywords[], min_confidence}, pipeline: {nodes[], edges[], conditional_edges[], degradation_edges[]}), `DomainPlan`(domain_id, domain_name, knowledge_base_id, confidence, reason), `DomainResult`(domain_id, domain_name, candidates: list[CandidateChunk], contributed_to_answer: bool, error: str|null)

### 2.13 Repository（3.13）

**目录**：`repository/pipeline/`

- [ ] `repository/pipeline/pipeline_repo.py` — `PipelineRepository(BaseRepository)`：CRUD 方法：`create(pipeline)`, `get_by_id(id, tenant_id)`, `list_by_tenant(tenant_id, filters)`, `update(id, data, tenant_id)`, `delete(id, tenant_id)`, `update_active_version(id, version, tenant_id)`。所有方法注入 `tenant_id` 过滤。
- [ ] `repository/pipeline/version_repo.py` — `PipelineVersionRepository(BaseRepository)`：CRUD 方法：`create(version)`, `list_by_pipeline(pipeline_id)`, `get_by_version(pipeline_id, version_number)`, `get_latest(pipeline_id)`, `get_for_compare(pipeline_id, v1, v2)`。
- [ ] `repository/pipeline/compound_repo.py` — `CompoundNodeRepository(BaseRepository)`：CRUD 方法：`create(node)`, `list_by_tenant(tenant_id)`, `get_by_id(id, tenant_id)`, `update(id, data, tenant_id)`, `delete(id, tenant_id)`, `import_from_json(tenant_id, owner_id, json_data)`。

### 2.14 服务层（3.14）

**目录**：`service/pipeline/`

- [ ] `service/pipeline/pipeline_service.py` — `PipelineService`：方法：`create(data, auth) → PipelineRead`（创建管道 + 初始 v1 配置快照）、`get(id, auth) → PipelineRead`（含当前版本完整配置）、`list(auth, filters) → PipelineList`、`update(id, data, auth) → PipelineRead`（保存 → 自动版本递增 + 变更说明校验）、`delete(id, auth)`（删除管道及其所有版本 + 检查发布 URL 引用）、`get_versions(id, auth) → list[PipelineVersionListItem]`、`get_version(id, v, auth) → PipelineVersionRead`、`rollback(id, v, auth) → PipelineVersionRead`（从 v 复制配置为新版本+1）、`compare(id, v1, v2, auth) → VersionCompareResult`。
- [ ] `service/pipeline/compound_service.py` — `CompoundNodeService`：方法：`create(data, auth) → CompoundNodeRead`、`list(auth) → list[CompoundNodeRead]`、`get(id, auth) → CompoundNodeRead`、`delete(id, auth)`、`export_to_json(id, auth) → dict`、`import_from_json(data, auth) → CompoundNodeRead`。
- [ ] `service/pipeline/validation_service.py` — `PipelineValidationService`：方法：`validate(id, auth) → ValidationResult`（校验管道配置：结构→节点→边→编译）、`dry_run(id, auth) → DryRunResult`（不实际执行检索，仅验证管道可编译 + 节点配置合法）。

### 2.15 控制器（3.15）

**目录**：`controller/pipeline/`

- [ ] `controller/pipeline/pipeline_controller.py` — 路由组 `/api/v1/pipelines`：
  - `POST /` — 创建管道
  - `GET /` — 管道列表（query params: page, size, status, search）
  - `GET /{id}` — 获取管道详情
  - `PUT /{id}` — 更新管道配置（触发版本递增）
  - `DELETE /{id}` — 删除管道
  - `GET /{id}/versions` — 版本列表
  - `GET /{id}/versions/{v}` — 获取指定版本
  - `POST /{id}/rollback/{v}` — 回滚到指定版本
  - `POST /{id}/validate` — 校验管道配置
  - `POST /{id}/dry-run` — 干运行
  - `POST /compare` — 对比两个版本（body: {pipeline_id, v1, v2}）
- [ ] `controller/pipeline/node_type_controller.py` — 路由组 `/api/v1/pipeline`：
  - `GET /node-types` — 返回所有已注册节点类型及参数 Schema（供编辑器面板使用）
- [ ] `controller/pipeline/compound_controller.py` — 路由组 `/api/v1/compound-nodes`：
  - `GET /` — 复合节点列表
  - `POST /` — 创建复合节点
  - `GET /{id}` — 获取复合节点
  - `PUT /{id}` — 更新复合节点
  - `DELETE /{id}` — 删除复合节点
  - `POST /import` — 导入复合节点 JSON
  - `GET /{id}/export` — 导出复合节点 JSON

---

## 3. 关键实现细节

### 3.1 Kahn 拓扑排序算法

PipelineCompiler 使用 Kahn 算法对节点图进行拓扑排序，同时检测环路。

```
输入：nodes: list[Node], edges: list[Edge]
输出：sorted_ids: list[str]（拓扑排序后的节点 ID 列表）

算法：
1. 构建邻接表 adjacency[node_id] = set[downstream_node_ids]
2. 计算入度 indegree[node_id] = 依赖它的上游节点数
3. 初始化队列 queue = [所有 indegree=0 的节点 ID]
4. while queue 非空：
   a. 弹出节点 n
   b. sorted_ids.append(n)
   c. for 每个 n 的下游节点 m：
      i. indegree[m] -= 1
      ii. if indegree[m] == 0: queue.append(m)
5. if len(sorted_ids) < len(nodes): 存在环路 → 抛出 PipelineCompilationError("管道包含循环依赖: [环路节点]")
6. return sorted_ids
```

实现位置：`PipelineCompiler._kahn_sort()`

### 3.2 并行组检测

拓扑排序后，识别可以并行执行的节点组——同层中无相互依赖的节点可以 `asyncio.gather` 并发执行。

```
输入：sorted_ids, adjacency, indegree_original
输出：parallel_groups: list[list[str]]

算法：
1. 遍历 sorted_ids，对每个节点：
   - 当前组 = 所有 indegree_original 相同且相互不在对方邻接表中的节点
2. 按 indegree 分组，每组内的节点可并行
3. 返回分组列表

实现简化版：
- 对于域分发节点产生的多个域管道：不通过静态图分析，而是运行时用 asyncio.gather 并行
- 静态分析仅用于聚合层节点的并行组识别
```

实现位置：`PipelineCompiler._detect_parallel_groups()`

实际并行执行在运行时的 `_execute_parallel_domains()` 中实现，而非编译时。

### 3.3 条件边求值

条件边在节点执行后通过 `_resolve_next_node()` 动态决定路由。

```python
def _resolve_next_node(self, current_node: str, state: PipelineState,
                        plan: ExecutionPlan) -> str | None:
    routes = plan.conditional_routes.get(current_node, [])
    for route in routes:
        if route.condition == "cache_hit" and state.metadata.get("cache_hit"):
            return route.target_node_id
        if route.condition == "cache_miss" and not state.metadata.get("cache_hit"):
            return route.target_node_id
        if route.condition.startswith("intent_route:"):
            label = route.condition.split(":", 1)[1]
            if label in state.intent_labels:
                return route.target_node_id
    return None  # 无匹配条件，走默认数据流边
```

条件类型一览：

| 条件类型 | 来源节点 | 求值逻辑 | 分支 |
|---------|---------|---------|------|
| `cache_hit` | `semantic_cache` | `state.metadata.get("cache_hit") == True` | → `unified_generate` |
| `cache_miss` | `semantic_cache` | `state.metadata.get("cache_hit") == False` | → 检索链首节点 |
| `intent_route:label` | `intent_classify` | `label in state.intent_labels` | → 对应检索策略节点 |

### 3.4 降级链

降级逻辑由 `NodeExecutorWrapper` 在节点执行外层处理，不在节点内部。

```python
async def execute(self, context: NodeContext) -> NodeResult:
    try:
        result = await self._executor.execute(context)
        context.trace_span.record_success()
        return result
    except Exception as e:
        strategies = self._degradation.get_chain(context.node_id)
        # strategies 按优先级排列：[skip_node, reroute, degrade_cache, abort]
        for strategy in strategies:
            try:
                result = await self._apply_strategy(strategy, context, e)
                context.trace_span.record_degraded(strategy)
                return result
            except Exception:
                continue  # 当前策略也失败 → 尝试下一个
        # 所有降级策略均失败
        raise NodeExecutionError(context.node_id, e)

async def _apply_strategy(self, strategy: str, context: NodeContext,
                           error: Exception) -> NodeResult:
    if strategy == "skip_node":
        return NodeResult(output=context.input_data, degraded=True,
                          degradation_strategy="skip_node",
                          degradation_reason=str(error))
    elif strategy == "reroute":
        alt_node_id = self._config["degradation"]["alternate_node"]
        alt_context = context.clone_with_node(alt_node_id)
        alt_executor = NodeRegistry.create_executor(alt_node_id)
        return await alt_executor.execute(alt_context)
    elif strategy == "degrade_cache":
        cached = await self._degradation.get_last_cached(context.node_id,
                                                          context.tenant_id)
        if cached is None:
            raise ValueError("无可用缓存")
        return NodeResult(output=cached, degraded=True,
                          degradation_strategy="degrade_cache")
    elif strategy == "abort":
        raise NodeExecutionError(context.node_id, error)
```

降级链式传递：A 降级到 B（reroute），B 也可有降级策略（B 返回 NodeResult 时 degraded=True），但不再触发 B 的降级（避免无限递归）。

### 3.5 域分发并行执行

`DomainDispatchExecutor` 通过 `asyncio.gather` 并行启动各域管道。

```python
async def _execute_parallel(self, domain_plans: list[DomainPlan],
                             context: NodeContext, timeout_ms: int,
                             max_concurrency: int) -> list[DomainResult]:
    semaphore = asyncio.Semaphore(max_concurrency)

    async def run_domain(plan: DomainPlan) -> DomainResult:
        async with semaphore:
            domain_context = context.clone_for_domain(
                domain_id=plan.domain_id,
                knowledge_base_id=plan.knowledge_base_id,
            )
            try:
                result = await asyncio.wait_for(
                    self._execute_single_domain(plan, domain_context),
                    timeout=timeout_ms / 1000  # 转换为秒
                )
                return DomainResult(
                    domain_id=plan.domain_id,
                    domain_name=plan.domain_name,
                    candidates=result.candidates,
                    contributed_to_answer=len(result.candidates) > 0,
                    error=None,
                )
            except asyncio.TimeoutError:
                return DomainResult(
                    domain_id=plan.domain_id,
                    domain_name=plan.domain_name,
                    candidates=[],
                    contributed_to_answer=False,
                    error=f"域管道超时 ({timeout_ms}ms)",
                )

    results = await asyncio.gather(*[run_domain(p) for p in domain_plans],
                                    return_exceptions=False)
    return list(results)
```

关键点：`timeout_ms` 作用于每个域管道，非总时间。`max_concurrency` 通过 `asyncio.Semaphore` 控制并发上限。

### 3.6 单域快捷路径检测与路径优化

检测逻辑在 `query_analyzer` 执行后：

```python
if len(state.domain_plans) == 1:
    state.shortcut_activated = True
    # 执行顺序路由到 shortcut_edge: query_analyzer → unified_generate
    # 跳过的节点：domain_dispatch, cross_fusion, cross_dedup, conflict_detect
```

PipelineCompiler 在 build_execution_plan 阶段为 single-domain 场景预建快捷路由：

```python
# 在 ExecutionPlan 的 conditional_routes 中：
plan.conditional_routes["query_analyzer"] = [
    ConditionalRoute(
        condition="single_domain",
        evaluate=lambda s: len(s.domain_plans) == 1,
        target_node_id="unified_generate"
    )
]
```

运行时 `_resolve_next_node` 检测到 `single_domain` 条件满足后，直接跳到 `unified_generate`，跳过中间 4 个聚合节点。

---

## 4. 节点实现优先级

推荐按以下顺序实现，确保最快形成端到端闭环：

### 第 1 优先级：闭环最小链路（Retrieval + 核心 Aggregation）
```
domain_dispatch → vector_search / bm25_search / hybrid_search → unified_generate
```
实现即可完成单域搜索全链路验证。

1. **检索节点**：`bm25_search`、`vector_search`、`hybrid_search`、`result_fusion`
2. **聚合节点**：`query_analyzer`、`domain_dispatch`、`unified_generate`

### 第 2 优先级：聚合层补全（Cross-domain）
3. **聚合节点**：`cross_fusion`、`cross_dedup`、`conflict_detect`

### 第 3 优先级：查询理解节点
4. **查询节点**：`query_rewrite`、`synonym_expand`、`query_decompose`、`term_normalize`、`intent_classify`、`stopword_filter`、`query_expand`

### 第 4 优先级：质量增强节点
5. **质量节点**：`rerank`、`dedup`、`hallucination_check`、`citation_verify`

### 第 5 优先级：安全合规节点
6. **安全节点**：`sensitive_filter`、`pii_mask`、`content_audit`

### 第 6 优先级：性能与合成节点
7. **性能节点**：`semantic_cache`、`rate_limiter`
8. **合成节点**：`structured_output`、`multimodal_search`

---

## 5. 测试策略

### 5.1 单元测试

**每节点执行器测试**（28 个 × 至少每个 3 个测试 = ~84 测试用例）：
- `test_validate_config_valid`：合法配置返回空错误列表
- `test_validate_config_invalid`：非法配置返回非空错误列表（如 `top_k=-1`、`similarity_threshold=2.0`、未知 strategy 等）
- `test_execute_with_mock_deps`：Mock 依赖（VectorStoreAdapter、LLM、EmbeddingEngine）后验证输出结构和元数据

**Kahn 排序测试**：
- `test_kahn_sort_linear_chain`：线性链 `A→B→C` → 输出 `[A, B, C]`
- `test_kahn_sort_diamond`：菱形结构 `A→B, A→C, B→D, C→D` → 输出中 A 在最前，D 在最后，B/C 顺序不固定
- `test_kahn_sort_circular_dependency`：环形 `A→B→A` → 抛出 `PipelineCompilationError`
- `test_kahn_sort_complex_dag`：复杂 10+ 节点的多域管道结构

**条件边路由测试**：
- `test_cache_hit_routes_to_unified_generate`：语义缓存命中 → 跳过检索链
- `test_cache_miss_routes_to_retrieval`：语义缓存未命中 → 进入检索链
- `test_intent_route_classifies_correctly`：意图分类匹配 → 路由到对应检索策略

**降级链测试**：
- `test_degradation_skip_node`：节点失败 → skip_node → 上游输出直传
- `test_degradation_reroute`：节点失败 → reroute → 备选节点执行
- `test_degradation_cache_fallback`：节点失败 → degrade_cache → 返回缓存
- `test_degradation_abort`：节点失败 → abort → 抛出异常
- `test_degradation_chain_exhausted`：所有降级策略均失败 → 抛出 `DegradationChainExhaustedError`

**配置覆盖测试**：
- `test_l3_overrides_l2`：API 参数覆盖管道配置
- `test_l2_overrides_l1`：管道配置覆盖租户默认
- `test_l0_fallback`：无更高层配置时使用 NODE_DEFAULTS

### 5.2 集成测试

**完整管道编译 + 执行**（使用测试知识库数据）：
- `test_compile_and_execute_single_domain_pipeline`：单域管道编译通过 + 执行返回结果
- `test_compile_and_execute_multi_domain_pipeline`：2 域管道编译通过 + 并行执行返回合并结果
- `test_compile_and_execute_with_conditional_edges`：带条件边的管道正确路由
- `test_compile_and_execute_with_degradation`：某节点模拟失败后降级链触发

**单域快捷路径**：
- `test_single_domain_shortcut_activated`：单域查询触发快捷路径，跳过 4 个聚合节点，响应标记 `shortcut_activated: true`
- `test_multi_domain_no_shortcut`：多域查询不触发快捷路径

**域并行**：
- `test_domains_execute_in_parallel`：用 2 个 domain 各自 sleep 模拟延迟，验证 `total_time ≈ max(sleep_1, sleep_2)`，非 `sum(sleep_1, sleep_2)`

**权限过滤**：
- `test_domain_dispatch_filters_by_role`：角色无权访问某域 → 该域不激活
- `test_superadmin_sees_all_domains`：超管不过滤，所有域激活

### 5.3 关键测试场景（≥10 个）

| # | 场景 | 验证点 |
|---|------|--------|
| 1 | 单域查询：`query_analyzer` → 1 个域 → 域管道 → `unified_generate` | 快捷路径触发，跳过 cross_fusion/cross_dedup/conflict_detect |
| 2 | 双域并行查询：`query_analyzer` → 2 个域 → 并行 → `cross_fusion` → `unified_generate` | 两个域异步并发，结果融合 |
| 3 | 语义缓存命中：查询命中缓存，跳过检索链 | `cache_hit` 条件边 → 直接到 `unified_generate` |
| 4 | 语义缓存未命中：查询未命中缓存，走检索链 | `cache_miss` 条件边 → 到 `bm25_search` |
| 5 | 意图路由：`intent_classify` 识别到 "医学查询" → 路由到特定检索策略 | `intent_route:medical` → 对应检索节点 |
| 6 | 节点降级 skip：`query_rewrite`（LLM 调用）超时 → skip_node 直传原查询 | 降级事件写入追踪，输出无改写 |
| 7 | 节点降级 reroute：主向量检索节点失败 → reroute 到备选向量检索节点（不同模型） | 备选节点执行成功 |
| 8 | 管道编译失败：依赖环 `A→B→A` → 编译失败 | `PipelineCompilationError` 包含环路节点 |
| 9 | 权限裁剪：用户无 `visible_roles` 交集 → 该域管道不执行 | 过滤域不激活，filtered_domains 计数 |
| 10 | 冲突检测：两个域返回矛盾信息 → `conflict_detect` 标记 | `ConflictReport.conflicts` 非空 |
| 11 | 配置覆盖：API `params.top_k=3` 覆盖管道配置 `top_k=10` | 检索返回 3 条结果 |
| 12 | 超时控制：某域管道超过 `timeout_ms=500` → 标记超时，不影响其他域 | 超时域返回 candidates=[] + error="超时" |
| 13 | 版本回滚：v3 回滚到 v1 → 创建 v4（= v1 配置的副本） | v4.config_snapshot == v1.config_snapshot |
| 14 | 版本对比：v1 vs v3 → 返回差异列表 | 新增/删除/修改的节点和参数 |
| 15 | 干运行：无效节点类型 → 返回错误位置 | 响应包含错误节点 ID + 未知 type + 原因 |

---

## 6. 验收检查点

### 6.1 编译正确性

- [ ] 线性链、菱形、复杂图全部正确拓扑排序
- [ ] 环路被正确检测并报告具体节点
- [ ] 28 种节点类型全部在 NodeRegistry 中注册
- [ ] 未注册的节点类型导致编译失败，错误消息含具体 node_id 和 type
- [ ] invalid config（如 `top_k=0`、`similarity_threshold=-1`、未知 `fusion_method`）编译失败，错误含具体参数路径

### 6.2 执行正确性

- [ ] 单域管道执行返回结果，shortcut_activated=true
- [ ] 多域管道并行执行，总耗时 ≤ max(各域耗时) + 聚合开销（验证并发性）
- [ ] 条件边按求值结果正确路由（cache_hit/cache_miss/intent_route 三种类型）
- [ ] 降级链按优先级顺序尝试（skip_node → reroute → degrade_cache → abort）
- [ ] 降级事件写入 Tracing 系统（span.degraded=true + degradation_strategy 字段）
- [ ] 单节点超时不阻塞其他节点

### 6.3 API 完整性

- [ ] 管道 CRUD（创建/列表/详情/更新/删除）全部可调用，返回统一响应格式
- [ ] 管道保存后版本号自动递增，change_log 写入 `pipeline_versions` 表
- [ ] 版本回滚创建新版本（不覆盖历史），新版本 config_snapshot = 原版本快照
- [ ] 版本对比返回结构化差异（新增/删除/修改的节点+参数+边）
- [ ] 管道校验端点返回错误位置（哪个节点的什么参数不合法）
- [ ] 干运行端点验证可编译性，不实际执行检索
- [ ] 复合节点增删改查 + 导入导出 JSON
- [ ] 删除有发布 URL 引用的管道返回明确错误（含引用 URL 列表）

### 6.4 代码质量

- [ ] 所有实体类在 `schemas/pipeline/` 下，无 controller/service/core 中定义 BaseModel
- [ ] 单类 ≤ 500 行（如 `compiler.py` 方法数较多需拆分为多个文件）
- [ ] 所有业务异常继承 `AppException`
- [ ] 全中文注释
- [ ] `PipelineCompiler._merge_params()` 实现 L3 > L2 > L1 > L0 优先级覆盖

### 6.5 追踪集成

- [ ] 每个节点执行产生一个 Span，包含 `node_id`、`node_type`、`domain_id`、`duration_ms`
- [ ] 降级事件在 Span 中标记 `degraded=true` + `degradation_strategy`
- [ ] pipeline_id 和 pipeline_version 注入所有子 Span

### 6.6 配置层级

- [ ] `NODE_DEFAULTS` 包含全部 28 种节点类型的 L0 默认值
- [ ] 运行时按 L3 > L2 > L1 > L0 优先级合并参数
- [ ] L3 参数仅白名单允许覆盖（出于安全考虑）

### 6.7 边界条件

- [ ] 空域列表（所有域被权限过滤）→ 聚合层正常完成，返回空结果
- [ ] 单域 + 权限过滤后该域不激活 → 返回空结果 + shortcut_activated=true（或 false，因激活域为 0）
- [ ] 所有节点失败且降级链耗尽 → 返回错误，非 500 崩溃
- [ ] L3 传入非法参数名（非白名单）→ 忽略（不覆盖），非 400 错误

---

## 7. 配套文件清单

Phase 3 预计新建文件约 40 个：

| 类别 | 文件数 | 文件 |
|------|--------|------|
| 核心框架 | 8 | `node_context.py`, `node_result.py`, `base_node.py`, `registry.py`, `compiled_pipeline.py`, `exceptions.py`, `defaults.py`, `degradation.py` |
| 编译器 | 1 | `compiler.py` |
| 节点执行器 | 28 | `query/` 7个, `retrieval/` 5个, `security/` 3个, `quality/` 4个, `performance/` 2个, `synthesis/` 1个, `aggregation/` 6个 |
| 注册 | 1 | `__init__.py`（注册 28 种节点） |
| 数据模型 | 3 | `models/pipeline.py`, `pipeline_version.py`, `compound_node.py` |
| Schemas | 6 | `schemas/pipeline/pipeline.py`, `version.py`, `node.py`, `edge.py`, `compound.py`, `domain.py` + `__init__.py` |
| Repository | 3 | `repository/pipeline/pipeline_repo.py`, `version_repo.py`, `compound_repo.py` |
| 服务层 | 3 | `service/pipeline/pipeline_service.py`, `compound_service.py`, `validation_service.py` |
| 控制器 | 2 | `controller/pipeline/pipeline_controller.py`, `compound_controller.py` |

**总计**：约 55 个文件（含 `__init__.py` 等辅助文件）

---

## 8. 与其他阶段的接口

| 接口方向 | 阶段 | 依赖内容 |
|---------|------|---------|
| **输入** | Phase 0 | 基础设施：`api/json_response.py`、`middleware/exception_handler.py`、`core/tracing/`、`core/config/`、`core/llm/` |
| **输入** | Phase 1 | 权限：`core/auth/rbac.py`、`middleware/auth_middleware.py`、`repository/base.py`（tenant_id 注入） |
| **输入** | Phase 2 | 知识库：`core/knowledge_base/vector_store/`（VectorStoreAdapter）、`core/knowledge_base/bm25_index.py`、`core/knowledge_base/acl_filter.py`、`core/knowledge_base/embedding/engine.py` |
| **输出** | Phase 4 | 搜索 API 调用 `PipelineCompiler.compile()` + `PipelineCompiler.execute()` |
| **输出** | Phase 7 | RAG 评估改造：`service/rag_eval/run/executor.py` 替换为调用 `PipelineCompiler` |

---

## 9. 变更历史

| 日期 | 变更 |
|------|------|
| 2026-05-14 | 初始创建：基于 implementation-checklist.md Phase 3 任务清单 + implementation-plan-detail.md §1 + requirements/01-pipeline-model-and-engine.md + ADR-001/002 |
