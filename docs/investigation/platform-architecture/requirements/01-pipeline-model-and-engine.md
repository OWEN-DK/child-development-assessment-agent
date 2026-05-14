# 01 — 管道模型与执行引擎

> **定位**：定义管道的数据结构、节点体系、配置格式和运行时执行逻辑。编辑器消费这些定义构建 UI，执行引擎消费 JSON 配置执行搜索。
> **与核心目标的关系**：实现 [核心目标 §四](./core-objectives.md#四管道编辑与发布可视化构建--配置输出-url) 的管道模型部分，支撑多业务域聚合的运行时。

---

## 配置层级

管道系统有四层配置，覆盖优先级从高到低：

| 层级 | 谁配置 | 存储位置 | 示例 |
|------|--------|---------|------|
| **L3: API 参数** | 调用方 | 请求体 `params` 字段 | `top_k`、`temperature`、`filters` |
| **L2: 管道配置** | 租户 editor | MySQL `pipeline_versions.config_snapshot` | 节点参数、域权重、条件边 |
| **L1: 租户覆盖** | 租户 admin | MySQL 全局配置表 | 租户级 LLM 模型、提示词模板 |
| **L0: 平台默认** | 超管 / 系统内置 | `.env` 兜底 + 代码常量 | 节点默认值、系统提示词、超时时间 |

**覆盖规则**：L3 > L2 > L1 > L0。L2（管道配置）是日常使用的主要层级——租户 editor 在管道编辑器中调整节点参数。L0/L1 提供默认值，L3 仅白名单参数允许 API 覆盖。

**参数表标注说明**：`[L0]`=平台默认，不可在编辑器中改。`[L1]`=租户级可覆盖。`[L2]`=管道编辑器中可配。`[L3]`=API 白名单参数。

---

## 1. 功能清单

### 1.1 节点体系（28 种，全部可选）

#### 域内节点（22 种，6 类）

**查询理解（7 种）**：

| 节点 | 类型标识 | 输入 → 输出 | 可配置参数 | 默认值 |
|------|---------|------------|-----------|--------|
| 查询改写 | `query_rewrite` | RawQuery → QueryVariant[] | `model` `prompt_template` `max_retries` | model=默认LLM, max_retries=2 |
| 同义词扩展 | `synonym_expand` | QueryVariant → ExpandedQuery | `synonym_source` `max_synonyms` `expansion_mode` | max_synonyms=5, mode=key_terms |
| 查询分解 | `query_decompose` | ComplexQuery → SubQuery[] | `model` `max_subqueries` `decomposition_strategy` | max_subqueries=5, strategy=auto |
| 术语标准化 | `term_normalize` | RawQuery → NormalizedQuery | `terminology_source` `normalize_mode` `model` | mode=both |
| 意图分类 | `intent_classify` | Query → IntentLabel[] | `model` `categories` `routing_rules` | — |
| 禁用词过滤 | `stopword_filter` | Query → FilteredQuery | `stop_words` `enabled` `case_sensitive` | enabled=false |
| 查询扩展 | `query_expand` | Query → QueryVariant[] | `model` `expansion_count` `expansion_method` | expansion_count=3 |

> **配置说明**：所有节点参数默认 [L2]（管道编辑器中可配）。标注 `model` 的参数同时支持 [L1]（租户 admin 在系统配置中设默认模型，L2 不设时用 L1）。`prompt_template` 为 [L1]（提示词模板在系统配置中统一管理，L2 只能从已有模板列表中选择）

**检索策略（5 种）**：

| 节点 | 类型标识 | 输入 → 输出 | 可配置参数 | 默认值 |
|------|---------|------------|-----------|--------|
| BM25 检索 | `bm25_search` | Query → CandidateSet | `top_k`、`k1`(默认1.5)、`b`(默认0.75)、`field_weights`(title/body)、`score_threshold` | top_k=10, k1=1.5, b=0.75 |
| 向量检索 | `vector_search` | Query → CandidateSet | `embedding_model`、`top_k`、`similarity_threshold`、`similarity_metric`(cosine/euclidean/dot)、`collection_name` | top_k=10, metric=cosine |
| 混合检索 | `hybrid_search` | Query → CandidateSet | `vector_weight`、`keyword_weight`、`top_k`、`fusion_method`(rrf/weighted_sum/linear)、`rrf_k` | vector_weight=0.6, keyword_weight=0.4, rrf_k=60 |
| 多模态检索 | `multimodal_search` | Query → CandidateSet | 各模态 `weight`(text/image/table)、各模态 `top_k`、`fusion_method` | — |
| 结果融合 | `result_fusion` | CandidateSet[] → CandidateSet | `fusion_method`(rrf/weighted_sum/linear)、各分支 `weight`、`final_top_k` | method=rrf |

**安全合规（3 种）—— 不拖入管道即跳过**：

| 节点 | 类型标识 | 输入 → 输出 | 可配置参数 | 默认值 |
|------|---------|------------|-----------|--------|
| 敏感词过滤 | `sensitive_filter` | CandidateSet → CandidateSet | `word_list`(列表/导入/正则)、`filter_mode`(remove/mask/flag)、`apply_to`(query/results/both) | mode=remove, apply_to=results |
| PII 脱敏 | `pii_mask` | CandidateSet → CandidateSet | `target_types`(phone/id_card/name/email/address/bank_card多选)、`mask_char`、`preserve_pattern` | mask_char=*, target_types=all |
| 内容审核 | `content_audit` | CandidateSet → CandidateSet | `model`(可设为none走规则)、`audit_rules`(porn/violence/politics/illegal/discriminate/ad多选)、`action`(filter/flag/reject)、`threshold` | threshold=0.7, action=flag |

**质量增强（4 种）**：

| 节点 | 类型标识 | 输入 → 输出 | 可配置参数 | 默认值 |
|------|---------|------------|-----------|--------|
| 重排序 | `rerank` | CandidateSet → CandidateSet | `model`、`initial_k`、`final_k` | initial_k=30, final_k=5 |
| 去重 | `dedup` | CandidateSet → CandidateSet | `method`(minhash/embedding)、`threshold`、`scope`(intra_domain/cross_doc/both) | threshold=0.85, method=minhash |
| 幻觉检测 | `hallucination_check` | CandidateSet → CandidateSet | `model`、`threshold`、`action`(filter/flag/both) | threshold=0.5, action=flag |
| 引用验证 | `citation_verify` | CandidateSet → CandidateSet | `mode`(strict/lax)、`model` | mode=lax |

**性能优化（2 种）—— 可插入管道任意位置**：

| 节点 | 类型标识 | 输入 → 输出 | 可配置参数 | 默认值 |
|------|---------|------------|-----------|--------|
| 语义缓存 | `semantic_cache` | Query → CachedResult|None | `cache_backend`(redis/memory)、`similarity_threshold`、`ttl`、`cache_key_strategy`(exact/semantic)、`max_cache_size`、`cache_key_scope`(role_aware/role_agnostic) | ttl=3600, cache_key_scope=role_aware |
| 速率限制 | `rate_limiter` | Query → Query|RateLimitError | `max_qps`、`algorithm`(sliding_window/token_bucket/leaky_bucket)、`scope`(per_domain/per_pipeline/per_user)、`action_on_limit`(queue/reject/degrade_cache) | algorithm=token_bucket |

**答案合成（1 种）**：

| 节点 | 类型标识 | 输入 → 输出 | 可配置参数 | 默认值 |
|------|---------|------------|-----------|--------|
| 结构化输出 | `structured_output` | CandidateSet → StructuredResult | `output_format`(json/table/markdown/custom_schema)、`schema_definition`(JSON Schema)、`model`、`strict_mode` | format=json |

> **全部节点参数配置层级**：`model` 类型参数为 [L2]（可选 L1 覆盖），`prompt_template` 为 [L1]，其余参数为 [L2]。L0 默认值见各表"默认值"列。详见 [§配置层级](#配置层级)。

#### 聚合层节点（6 种，连接顺序可调）

| 节点 | 类型标识 | 输入 → 输出 | 可配置参数 | 默认值 |
|------|---------|------------|-----------|--------|
| 查询分析 | `query_analyzer` | RawQuery → DomainPlan[] | `model`、`max_domains`、`min_confidence`、`domain_keywords`(各域触发关键词) | max_domains=5, min_confidence=0.6 |
| 域分发 | `domain_dispatch` | DomainPlan[] → RoutedQuery[] | `parallel`、`timeout_ms`、`max_concurrency` | parallel=true, timeout_ms=3000 |
| 跨域融合 | `cross_fusion` | DomainResult[] → MergedSet | `fusion_method`(weighted_rrf/weighted_sum/priority_ordered)、各域`weight`、`rrf_k`、`final_top_k` | method=weighted_rrf, rrf_k=60 |
| 跨域去重 | `cross_dedup` | MergedSet → DedupedSet | `dedup_threshold`、`dedup_method`(minhash/embedding) | threshold=0.85 |
| 冲突检测 | `conflict_detect` | DedupedSet → ConflictReport | `model`、`enabled`、`conflict_threshold` | enabled=true |
| 统一答案合成 | `unified_generate` | DedupedSet+ConflictReport → Answer | `model`、`temperature`、`max_tokens`、`include_citations`、`citation_format` | temperature=0.3, include_citations=true |

### 1.2 条件路由（条件边）

节点输出决定下游分支。条件边在配置中以 `conditional_edges` 数组存储，画布以虚线显示。

| 条件类型 | 来源节点 | 条件表达式 | 典型分支目标 |
|---------|---------|-----------|------------|
| `cache_hit` | `semantic_cache` | 缓存命中=true | 跳过检索链 → 答案合成 |
| `cache_miss` | `semantic_cache` | 缓存命中=false | 走完整检索链 |
| `intent_route` | `intent_classify` | 分类标签匹配 | 各分类 → 对应检索策略 |

**约束**：
- 一个节点最多出 1 条普通数据流边 + N 条条件边
- 条件判断逻辑在节点内部完成，配置只定义分支映射
- 条件分支的汇聚节点需标注（多条条件边指向同一节点时编辑器自动校验合法性）

### 1.3 降级路径（降级边）

任意节点可配置一条降级边，定义主路径失败时的备选行为。画布以橙色虚线显示。

| 降级策略 | 行为 | 适用场景 |
|---------|------|---------|
| `skip_node` | 上游输出直传下游，跳过失败节点 | 非关键节点失败（如同义词扩展超时） |
| `reroute` | 路由到备选同类型节点 | 主模型不可用，切换到备选模型 |
| `degrade_cache` | 取最近一次成功缓存结果 | 检索链中断，用缓存兜底 |
| `abort`（默认） | 直接返回错误 | 关键节点失败不可降级 |

**约束**：
- 降级发生时记录告警日志，写入执行追踪
- 降级触发频率超过阈值（如连续 10 次）自动告警
- 支持降级链式传递：A 降级到 B，B 也可有自己的降级

### 1.4 复合节点

用户将固定节点组合保存为可复用单元。

**配置格式**：
```json
{
  "id": "compound_medical_search",
  "name": "标准医学检索组",
  "type": "compound",
  "expanded_nodes": [
    {"id": "inner_1", "type": "term_normalize", "config": {...}},
    {"id": "inner_2", "type": "hybrid_search", "config": {...}},
    {"id": "inner_3", "type": "rerank", "config": {...}}
  ],
  "internal_edges": [
    {"source": "inner_1", "target": "inner_2"},
    {"source": "inner_2", "target": "inner_3"}
  ],
  "exposed_ports": {
    "input": "inner_1",
    "output": "inner_3"
  }
}
```

**约束**：
- 修改复合节点内部配置不影响已部署实例（实例持有独立副本）
- 复合节点可嵌套（复合节点内包含复合节点），最多 3 层
- 导出/导入 JSON，支持跨用户共享

**复合节点与条件边/降级边的交互规则**：

| 场景 | 规则 |
|------|------|
| **条件边指向复合节点** | 允许。条件边连接到复合节点的 `exposed_ports.input`，数据进入复合节点内部后按 `internal_edges` 执行 |
| **条件边从复合节点出发** | 允许。复合节点的 `exposed_ports.output` 执行后，按条件边规则路由到下游 |
| **条件边指向复合节点内部子节点** | **禁止**。条件边只能连接到复合节点的 `exposed_ports`，不可穿透到内部。编辑器在连线时校验，若目标节点在复合节点内部则阻止连线 |
| **降级边指向复合节点** | 允许。复合节点整体失败时触发降级策略 |
| **降级边从复合节点出发** | 允许。复合节点整体可配置一条降级边 |
| **降级边指向复合节点内部子节点** | **禁止**。降级边只能连接到复合节点的 `exposed_ports` |
| **复合节点内部子节点的降级边** | 允许。复合节点展开态下，内部子节点可独立配置降级边（仅在展开态可编辑） |

**PipelineCompiler 处理**：
- 执行复合节点时，先展开内部节点图，按 `internal_edges` 拓扑排序执行
- 内部子节点的降级事件正常记录到追踪系统
- 复合节点整体的成功/失败状态 = 最后一个内部子节点（`exposed_ports.output`）的状态

### 1.5 管道版本管理

| 操作 | 行为 |
|------|------|
| 保存 | 自动递增版本号（v1, v2, v3...），弹出变更说明输入框 |
| 回滚 | 选择历史版本 → 复制为当前编辑版本（新版本号） |
| 对比 | 选择两个版本 → 列出节点差异（新增/删除/参数变更） |
| 发布绑定 | 发布 URL 绑定特定版本，修改不推送，手动切换 |

**数据模型**：
- `pipeline_version`：version_number (int, auto-increment per pipeline)、change_log、config_snapshot (full JSON)、created_at
- 当前活动版本存储在 pipeline 记录的 `active_version` 字段

### 1.6 单域快捷路径

查询分析节点检测到只涉及一个业务域时自动触发：
- 执行路径：`查询分析 → 域管道 → 统一答案合成`
- 跳过节点：域分发、跨域融合、跨域去重、冲突检测
- 响应中 `shortcut_activated: true`

### 1.7 PipelineCompiler（执行引擎）

**职责**：读取管道 JSON 配置 → 编译为可执行 DAG → 按拓扑顺序执行 → 收集结果。

**核心能力**：
- 拓扑排序：校验无环，生成执行顺序
- 域并发执行：`domain_dispatch` 节点并行启动各域管道，等待全部完成（受 timeout_ms 约束）
- 单域短路：检测激活域数=1 → 跳过聚合中间节点
- 条件边求值：节点执行后检查条件边，决定下一跳
- 降级处理：节点失败时检查降级边，执行降级策略
- 降级事件收集：记录所有降级事件用于追踪和告警
- 追踪注入：每个节点执行产生 Span，记录耗时和输入摘要

**约束**：
- 编译失败时返回具体错误位置（哪个节点的什么配置不合法）
- 域管道之间无共享状态，互不干扰
- 聚合层节点顺序由 edges 数组决定，不预设固定顺序
- 权限过滤在域分发节点执行时注入（见 [04-permission](./04-permission-and-multi-tenancy.md)）

### 1.8 节点注册机制

PipelineCompiler 通过 `NodeRegistry` 管理所有可用节点类型。新增节点类型是平台发版动作，需后端实现新节点类并注册。

**注册接口**：

```python
class NodeRegistry:
    """节点类型注册表。PipelineCompiler 编译时从此处查找节点执行器。"""

    _registry: dict[str, type[BaseNodeExecutor]] = {}

    @classmethod
    def register(cls, node_type: str, executor_class: type[BaseNodeExecutor]):
        """注册节点类型。发版时在模块初始化中调用。"""
        cls._registry[node_type] = executor_class

    @classmethod
    def get(cls, node_type: str) -> type[BaseNodeExecutor]:
        """查找节点执行器。未注册的类型抛出 NodeNotRegisteredError。"""
        if node_type not in cls._registry:
            raise NodeNotRegisteredError(f"节点类型 '{node_type}' 未注册")
        return cls._registry[node_type]

    @classmethod
    def list_types(cls) -> list[str]:
        """返回所有已注册的节点类型标识列表。"""
        return list(cls._registry.keys())
```

**节点执行器基类**：

```python
class BaseNodeExecutor(ABC):
    """所有节点执行器的基类。"""

    @abstractmethod
    async def execute(self, context: NodeContext) -> NodeResult:
        """执行节点逻辑。context 包含输入数据和节点配置。"""
        ...

    @abstractmethod
    def validate_config(self, config: dict) -> list[str]:
        """校验节点配置。返回错误列表，空列表表示合法。"""
        ...
```

**注册清单**（28 种节点全部在发版时注册）：

| 类别 | 注册的节点类型标识 | 执行器位置 |
|------|------------------|-----------|
| 查询理解 | `query_rewrite`, `synonym_expand`, `query_decompose`, `term_normalize`, `intent_classify`, `stopword_filter`, `query_expand` | `core/pipeline/nodes/query/` |
| 检索策略 | `bm25_search`, `vector_search`, `hybrid_search`, `multimodal_search`, `result_fusion` | `core/pipeline/nodes/retrieval/` |
| 安全合规 | `sensitive_filter`, `pii_mask`, `content_audit` | `core/pipeline/nodes/security/` |
| 质量增强 | `rerank`, `dedup`, `hallucination_check`, `citation_verify` | `core/pipeline/nodes/quality/` |
| 性能优化 | `semantic_cache`, `rate_limiter` | `core/pipeline/nodes/performance/` |
| 答案合成 | `structured_output` | `core/pipeline/nodes/synthesis/` |
| 聚合层 | `query_analyzer`, `domain_dispatch`, `cross_fusion`, `cross_dedup`, `conflict_detect`, `unified_generate` | `core/pipeline/nodes/aggregation/` |

**不可妥协**：
- 管道配置中引用未注册的节点类型 → 编译失败，返回 `NodeNotRegisteredError`
- 新增节点类型必须同时：(1) 实现 `BaseNodeExecutor`，(2) 调用 `NodeRegistry.register()`，(3) 在编辑器的节点面板中添加对应 UI 入口
- 运行时不允许动态注册节点（仅发版时静态注册）

---

## 2. 数据模型

### 2.1 管道配置（根对象）

```json
{
  "pipeline": {
    "id": "string",
    "name": "string",
    "type": "aggregation",
    "version": "int",
    "change_log": "string|null",
    "tenant_id": "string"
  },
  "domains": [
    {
      "id": "string",
      "name": "string",
      "knowledge_base_id": "string",
      "weight": "float (0-1)",
      "activation_rules": {
        "keywords": ["string"],
        "min_confidence": "float"
      },
      "pipeline": {
        "nodes": [],
        "edges": [],
        "conditional_edges": [],
        "degradation_edges": []
      }
    }
  ],
  "aggregation": {
    "nodes": [],
    "edges": [],
    "shortcut_edge": {"source": "query_analyzer", "target": "unified_generate"}
  }
}
```

### 2.2 节点（Node）

```json
{
  "id": "string (pipeline-unique)",
  "type": "string (28种类型标识之一)",
  "config": {},
  "display": {"x": 0, "y": 0}
}
```

### 2.3 边（Edge）

```json
{
  "id": "string",
  "source": "node_id",
  "target": "node_id",
  "type": "data | conditional | degradation",
  "condition": "cache_hit | cache_miss | intent_route:label",
  "strategy": "skip_node | reroute | degrade_cache | abort"
}
```

### 2.4 数据库表

| 表名 | 关键字段 |
|------|---------|
| `pipelines` | id, tenant_id, name, type, active_version, created_at, updated_at |
| `pipeline_versions` | id, pipeline_id, version_number, change_log, config_snapshot (JSON), created_at |
| `compound_nodes` | id, owner_id, name, config_snapshot (JSON), created_at |

---

## 3. API 端点

| 方法 | 路径 | 描述 |
|------|------|------|
| `POST` | `/api/v1/pipelines` | 创建管道 |
| `GET` | `/api/v1/pipelines` | 管道列表（按租户过滤） |
| `GET` | `/api/v1/pipelines/{id}` | 获取管道（含当前版本完整配置） |
| `PUT` | `/api/v1/pipelines/{id}` | 更新管道配置（触发版本递增） |
| `DELETE` | `/api/v1/pipelines/{id}` | 删除管道及其所有版本 |
| `GET` | `/api/v1/pipelines/{id}/versions` | 版本列表 |
| `GET` | `/api/v1/pipelines/{id}/versions/{v}` | 获取指定版本配置 |
| `POST` | `/api/v1/pipelines/{id}/rollback/{v}` | 回滚到指定版本 |
| `POST` | `/api/v1/pipelines/compare` | 对比两个版本（body: {pipeline_id, v1, v2}） |
| `POST` | `/api/v1/pipelines/{id}/validate` | 校验管道配置（不保存） |
| `POST` | `/api/v1/pipelines/{id}/dry-run` | 干运行（不实际执行检索，验证可编译性） |
| `GET` | `/api/v1/compound-nodes` | 用户复合节点列表 |
| `POST` | `/api/v1/compound-nodes` | 创建复合节点 |
| `DELETE` | `/api/v1/compound-nodes/{id}` | 删除复合节点 |
| `POST` | `/api/v1/compound-nodes/import` | 导入复合节点 JSON |
| `GET` | `/api/v1/compound-nodes/{id}/export` | 导出复合节点 JSON |

---

## 4. 执行追踪

每个管道执行产生以下追踪数据，写入 Tracing 系统（见 [07-infrastructure](./07-infrastructure-and-deployment.md)）：

| Span 字段 | 说明 |
|-----------|------|
| `pipeline_id` | 管道 ID |
| `pipeline_version` | 管道版本号 |
| `domain_id` | 域 ID（域内节点）或 null（聚合节点） |
| `node_id` | 节点 ID |
| `node_type` | 节点类型标识 |
| `input_summary` | 输入摘要（不记录完整内容，保护隐私） |
| `output_summary` | 输出摘要 |
| `duration_ms` | 节点执行耗时 |
| `error` | 错误信息（如有） |
| `degraded` | 是否降级 |
| `degradation_strategy` | 降级策略（如降级） |

---

## 5. 验收标准

- [ ] AC-1.1：所有 28 种节点（22 域内 + 6 聚合）在 PipelineCompiler 中可编译执行，各类型标识注册完整
- [ ] AC-1.2：条件路由正确求值——缓存命中走答案合成、未命中走检索链
- [ ] AC-1.3：降级路径触发时正确执行降级策略，降级事件写入追踪
- [ ] AC-1.4：降级频率超过阈值时触发告警（可观测：Prometheus 指标 + 告警通知）
- [ ] AC-1.5：复合节点展开后内部节点参数可独立修改，修改不影响其他管道实例
- [ ] AC-1.6：管道保存后版本号自增，回滚创建新版本（不覆盖历史）
- [ ] AC-1.7：单域查询触发快捷路径，跳过 4 个聚合中间节点，响应标注 `shortcut_activated: true`
- [ ] AC-1.8：聚合层节点顺序由 edges 数组决定，支持"先冲突检测再融合"和"先融合再冲突检测"两种拓扑
- [ ] AC-1.9：配置校验端点返回具体错误位置（哪个节点、哪个参数、什么问题）
- [ ] AC-1.10：域管道并发执行，总延迟 ≈ max(各域延迟) + 聚合开销，而非 sum(各域延迟)

---

## 6. 与其他模块的接口

| 被依赖 | 接口 |
|--------|------|
| [02-pipeline-editor](./02-pipeline-editor.md) | 编辑器通过 `/api/v1/pipelines` 读写管道配置；编辑器使用本模块的节点定义渲染面板 |
| [04-permission](./04-permission-and-multi-tenancy.md) | PipelineCompiler 在域分发节点调用权限模块注入过滤条件 |
| [05-search-api](./05-pipeline-publishing-and-search-api.md) | 搜索 API 调用 PipelineCompiler 执行管道 |
| [06-rag-evaluation](./06-rag-evaluation.md) | 评估引擎调用 PipelineCompiler 批量执行测试用例 |
