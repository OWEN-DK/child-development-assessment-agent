# Phase 8：安全/质量节点（后置）

> **定位**：在 Phase 3 管道引擎框架和核心检索链路闭环后，补齐剩余 10 个后置节点执行器及其参数表单。这些节点业务优先级较低，但构成完整 28 节点图。
> **前置阶段**：Phase 3（管道引擎核心框架 + 检索类节点 + 聚合节点已实现）
> **后置阶段**：Phase 9（超管前端）、Phase 10（ES/Milvus 后端扩展）
> **创建日期**：2026-05-14

---

## 1. 阶段目标

实现剩余 10 个节点执行器（安全合规 3 个 + 质量增强 4 个 + 性能优化 1 个 + 答案合成 1 个 + 检索策略 1 个），使全部 28 种节点类型完成注册，管道编辑器可拖拽使用。每个节点实现 `BaseNodeExecutor` 接口（`execute` + `validate_config`）、对应的前端参数表单组件、以及单元/集成测试。

与 Phase 3 实现的 18 个节点关系：

```
Phase 3 已实现（18）：
  查询理解(7): query_rewrite, synonym_expand, query_decompose, term_normalize,
                intent_classify, stopword_filter, query_expand
  检索策略(4):  bm25_search, vector_search, hybrid_search, result_fusion
  性能优化(1):  semantic_cache
  聚合层(6):    query_analyzer, domain_dispatch, cross_fusion, cross_dedup,
                conflict_detect, unified_generate

Phase 8 补全（10）：
  安全合规(3):  sensitive_filter, pii_mask, content_audit
  质量增强(4):  rerank, dedup, hallucination_check, citation_verify
  性能优化(1):  rate_limiter
  答案合成(1):  structured_output
  检索策略(1):  multimodal_search
```

---

## 2. 任务清单

> 每项任务对应 `implementation-checklist.md` Phase 8 条目。
> 标记：`[ ]` 未开始，`[~]` 进行中，`[x]` 已完成

### 2.1 安全合规节点（3 个）

- [ ] `nodes/security/__init__.py` — 模块初始化
- [ ] `nodes/security/sensitive_filter.py` — `SensitiveFilterExecutor` + `SensitiveFilterParameterForm.tsx`
- [ ] `nodes/security/pii_mask.py` — `PIIMaskExecutor` + `PIIMaskParameterForm.tsx`
- [ ] `nodes/security/content_audit.py` — `ContentAuditExecutor` + `ContentAuditParameterForm.tsx`

### 2.2 质量增强节点（4 个）

- [ ] `nodes/quality/__init__.py` — 模块初始化
- [ ] `nodes/quality/rerank.py` — `RerankExecutor` + `RerankParameterForm.tsx`
- [ ] `nodes/quality/dedup.py` — `DedupExecutor` + `DedupParameterForm.tsx`
- [ ] `nodes/quality/hallucination_check.py` — `HallucinationCheckExecutor` + `HallucinationCheckParameterForm.tsx`
- [ ] `nodes/quality/citation_verify.py` — `CitationVerifyExecutor` + `CitationVerifyParameterForm.tsx`

### 2.3 性能优化节点（1 个）

- [ ] `nodes/performance/rate_limiter.py` — `RateLimiterExecutor` + `RateLimiterParameterForm.tsx`

### 2.4 答案合成节点（1 个）

- [ ] `nodes/synthesis/__init__.py` — 模块初始化
- [ ] `nodes/synthesis/structured_output.py` — `StructuredOutputExecutor` + `StructuredOutputParameterForm.tsx`

### 2.5 检索策略节点（1 个）

- [ ] `nodes/retrieval/multimodal_search.py` — `MultimodalSearchExecutor` + `MultimodalSearchParameterForm.tsx`

### 2.6 节点注册更新

- [ ] 更新 `core/pipeline/__init__.py` — 注册新增 10 种节点类型到 `NodeRegistry`
- [ ] 更新 `core/pipeline/defaults.py` — 补充 10 种节点类型的 L0 默认参数值

### 2.7 前端参数表单（10 个）

- [ ] `features/pipeline/components/PropertyPanel/forms/SensitiveFilterParameterForm.tsx`
- [ ] `features/pipeline/components/PropertyPanel/forms/PIIMaskParameterForm.tsx`
- [ ] `features/pipeline/components/PropertyPanel/forms/ContentAuditParameterForm.tsx`
- [ ] `features/pipeline/components/PropertyPanel/forms/RerankParameterForm.tsx`
- [ ] `features/pipeline/components/PropertyPanel/forms/DedupParameterForm.tsx`
- [ ] `features/pipeline/components/PropertyPanel/forms/HallucinationCheckParameterForm.tsx`
- [ ] `features/pipeline/components/PropertyPanel/forms/CitationVerifyParameterForm.tsx`
- [ ] `features/pipeline/components/PropertyPanel/forms/RateLimiterParameterForm.tsx`
- [ ] `features/pipeline/components/PropertyPanel/forms/StructuredOutputParameterForm.tsx`
- [ ] `features/pipeline/components/PropertyPanel/forms/MultimodalSearchParameterForm.tsx`

### 2.8 前端表单注册更新

- [ ] 更新 `features/pipeline/components/PropertyPanel/PropertyPanel.tsx` — `NODE_PARAMETER_FORMS` 映射表追加 10 个新表单
- [ ] 更新 `features/pipeline/components/NodePanel/NodePanel.tsx` — 节点面板追加 10 种可拖拽节点（安全/质量/性能/合成/检索 分组）

---

## 3. 关键实现细节

### 3.1 敏感词过滤 (`sensitive_filter`)

| 维度 | 说明 |
|------|------|
| **文件** | `nodes/security/sensitive_filter.py` |
| **继承来源** | 新建。逻辑参考 `backend/src/service/content_audit_service.py:71-100` 的 `_local_audit()` 方法中正则匹配部分 |
| **输入类型** | `RawQuery`（上游用户查询字符串） |
| **输出类型** | `FilteredQuery`（字段：`clean_text: str`、`has_issues: bool`、`matched_words: list[str]`、`action: Literal["pass", "block", "redact"]`、`redacted_text: str | None`） |
| **执行逻辑** | 1. 从 `context.config` 读取 `word_list`（敏感词列表，来自数据库配置表或租户自定义）<br>2. 逐词正则匹配查询字符串<br>3. 根据 `action` 决定处理方式：`pass`=返回原查询并标记 has_issues、`block`=抛出 `NodeExecutionError` 阻断管道（可降级）、`redact`=用 `***` 替换匹配词后继续<br>4. 输出 `FilteredQuery` 含匹配详情和脱敏后文本 |
| **配置参数** | `word_list: list[str]`（敏感词列表）、`action: Literal["pass", "block", "redact"]`（默认 "pass"）、`case_sensitive: bool`（默认 false）、`match_mode: Literal["partial", "whole", "regex"]`（默认 "partial"）、`categories: list[str]`（仅检测指定类别的敏感词，空=全部） |
| **参数表单** | 敏感词管理：可添加/删除的标签列表 + 操作模式下拉（通过/拒绝/脱敏）+ 大小写敏感开关 + 匹配模式选择（部分匹配/全词匹配/正则） |

### 3.2 PII 脱敏 (`pii_mask`)

| 维度 | 说明 |
|------|------|
| **文件** | `nodes/security/pii_mask.py` |
| **继承来源** | 新建。一期 Python `re` 模块。预留 Rust `regex` crate + PyO3 扩展点（批量文档处理时启用，5-10x 加速，见 ADR-001）。保留 Python 回退路径 |
| **输入类型** | `str`（待脱敏文本，可来自 `Query` 或 `Answer`，由管道配置决定插在哪个位置） |
| **输出类型** | `MaskedText`（字段：`original: str`、`masked: str`、`detected_items: list[PIIDetection]`，其中 `PIIDetection` 含 `type: Literal["phone", "id_card", "email", "name", "address"]`、`matched_text: str`、`position: tuple[int, int]`） |
| **执行逻辑** | 1. 从 `context.config` 读取启用的脱敏类型列表 `detection_types`<br>2. 按顺序用预编译正则对文本做匹配（一期 Python `re`，大数据量时切 Rust `regex` crate）<br>3. 对匹配到的片段用替换模式（如手机号 `138****1234`）改写<br>4. 返回 `MaskedText`，包含原始文本、脱敏后文本、检测到的 PII 项列表 |
| **配置参数** | `detection_types: list[Literal["phone", "id_card", "email", "name", "address"]]`（默认全部）、`mask_char: str`（默认 `*`）、`preserve_header: bool`（保留首尾字符，默认 true）、`min_confidence: float`（0-1，仅姓名类模糊检测使用，默认 0.7） |
| **参数表单** | 多选框组（勾选检测类型：手机号/身份证/邮箱/姓名/地址）+ 脱敏字符输入 + 保留首尾开关 + 置信度滑动条 |

### 3.3 内容审核 (`content_audit`)

| 维度 | 说明 |
|------|------|
| **文件** | `nodes/security/content_audit.py` |
| **继承来源** | 改造自 `backend/src/service/content_audit_service.py`（约 177 行，继承核心逻辑 `audit_content()`、`_local_audit()`、`_external_audit()`，去除对 `settings.rag_config` 的直接依赖，转为从 `context.config` 读取） |
| **输入类型** | `AuditInput`（字段：`content: str`、`source: Literal["query", "retrieval_result", "answer"]`） |
| **输出类型** | `AuditResult`（字段：`passed: bool`、`reason: str`、`flags: list[AuditFlag]`，其中 `AuditFlag` 含 `category: str`、`level: Literal["info", "warning", "critical"]`、`matched: str`、`position: tuple[int, int] | None`） |
| **执行逻辑** | 1. 从 `context.config` 读取本地敏感词配置（word_list + categories）<br>2. 执行本地规则审核（与 `sensitive_filter` 不同，这里输出审核结果而非直接拒绝/修改）<br>3. 若 `enable_llm_audit=true`，调用 LLM 对内容做安全评估（审核提示词：评估内容是否包含不当信息，返回通过/不通过的结论）<br>4. 若 `enable_external_api=true` 且配置了外部审核 API，调用远程审核接口<br>5. 汇总各层审核结果：全部通过则 `passed=true`；任一不通过则 `passed=false` + 详细 flags |
| **配置参数** | `enable_llm_audit: bool`（默认 false）、`llm_model: str`（默认继承 LLM 工厂默认模型）、`audit_prompt_template: str`（审核提示词模板）、`enable_external_api: bool`（默认 false）、`external_api_url: str`、`external_api_key: str`、`strict_mode: bool`（true=任一 flag 即拒绝，false=仅 critical 级别拒绝，默认 true） |
| **参数表单** | LLM 审核开关 + 提示词模板文本区 + 外部 API 配置区（开关/URL/Key）+ 严格模式开关 |

### 3.4 重排序 (`rerank`)

| 维度 | 说明 |
|------|------|
| **文件** | `nodes/quality/rerank.py` |
| **继承来源** | 改造自 `backend/src/core/reranker.py`（约 380 行。继承 `CrossEncoderReranker`、`DashScopeReranker`、`create_reranker()` 工厂逻辑，去除对 `monitoring_service` 的直接依赖，转为通过 `context.trace_span` 记录指标） |
| **输入类型** | `list[CandidateChunk]`（上游检索节点输出的候选分块列表，每个含 `chunk_id`、`content`、`score`） |
| **输出类型** | `list[CandidateChunk]`（重排序后的候选列表，score 已更新为重排序分数） |
| **执行逻辑** | 1. 从 `context.config` 读取 provider（dashscope/local）、model_name、initial_k、final_k<br>2. 根据 provider 创建 `DashScopeReranker` 或 `CrossEncoderReranker` 实例（通过 `create_reranker()` 工厂，单例缓存）<br>3. 将 `CandidateChunk` 转为 reranker 可接受的 `NodeWithScore` 格式（content + score）<br>4. 调用 `rerank(query, nodes)` 执行重排序<br>5. 将 [0,1] 的 relevance_score 赋值回 `CandidateChunk.score`<br>6. 截取前 `final_k` 个返回<br>7. 记录重排序耗时到 `context.trace_span` |
| **配置参数** | `provider: Literal["dashscope", "local"]`（默认 "dashscope"）、`model_name: str`（默认 "qwen3-rerank" for dashscope / "BAAI/bge-reranker-v2-m3" for local）、`initial_k: int`（重排序输入候选数，默认 30）、`final_k: int`（重排序输出数，默认 5）、`dynamic_initial_k: bool`（根据查询长度动态调整，默认 true） |
| **参数表单** | 提供方下拉（DashScope API / 本地 Cross-Encoder）+ 模型名称输入 + initial_k 数字输入 + final_k 数字输入 + 动态 initial_k 开关 |

### 3.5 去重 (`dedup`)

| 维度 | 说明 |
|------|------|
| **文件** | `nodes/quality/dedup.py` |
| **继承来源** | 改造自 `backend/src/core/rag/dedup_engine.py`。一期 Python `datasketch` 库。预留 Rust MinHash + PyO3 扩展点（候选集 > 200 条时启用，5-10x 加速，见 ADR-001）。保留 Python 回退路径 |
| **输入类型** | `list[CandidateChunk]`（上游检索或融合后的候选分块列表） |
| **输出类型** | `DedupOutput`（字段：`items: list[CandidateChunk]`、`exact_dedup_count: int`、`minhash_dedup_count: int`、`total_removed: int`） |
| **执行逻辑** | 1. 从 `context.config` 读取方法配置和阈值<br>2. Step 1—精确去重 (O(n))：SHA-256 hash<br>3. Step 2—MinHash 近似去重 (O(n log n))（仅当 `use_minhash=true` 时执行）：<br>   a. 候选集 > 200 条 + USE_RUST → 走 Rust PyO3 路径<br>   b. 否则走 Python datasketch 路径<br>   c. 分词 → MinHash 签名 → LSH 索引 → 保留 score 更高的条目<br>4. 返回 `DedupOutput` 包含去重后列表和统计 |
| **配置参数** | `methods: list[Literal["exact_hash", "minhash"]]`（默认 ["exact_hash", "minhash"]）、`minhash_num_perm: int`（MinHash 签名维度，默认 128）、`minhash_threshold: float`（LSH 近似重复阈值 0-1，默认 0.7）、`dedup_by: Literal["content", "chunk_id"]`（去重依据字段，默认 "content"）、`keep_strategy: Literal["highest_score", "longest", "first"]`（重复项保留策略，默认 "highest_score"） |
| **参数表单** | 去重方法多选（精确哈希/MinHash）+ num_perm 数字输入 + 阈值滑动条 (0.5-0.99) + 去重字段选择 + 保留策略下拉 |

### 3.6 幻觉检测 (`hallucination_check`)

| 维度 | 说明 |
|------|------|
| **文件** | `nodes/quality/hallucination_check.py` |
| **继承来源** | 新建。通过 LLM 调用实现，提示词要求模型逐句比对答案与检索上下文的一致性 |
| **输入类型** | `HallucinationInput`（字段：`answer: str`、`context_chunks: list[str]`—上游检索或生成的大段文本） |
| **输出类型** | `HallucinationReport`（字段：`is_hallucinated: bool`、`hallucination_score: float`（0-1，越高越严重）、`issues: list[HallucinationIssue]`，其中 `HallucinationIssue` 含 `sentence: str`、`reason: str`、`severity: Literal["minor", "moderate", "critical"]`、`grounded: bool`） |
| **执行逻辑** | 1. 构建幻觉检测 prompt：将 `answer` 和 `context_chunks` 注入模板<br>2. 调用 LLM，要求输出结构化 JSON（含整体判断和逐句分析）<br>3. 使用 `json-repair` 修复可能的 JSON 格式错误<br>4. 解析为 `HallucinationReport`<br>5. 若 `hallucination_score >= block_threshold`，抛出 `NodeExecutionError` 阻断（可降级） |
| **配置参数** | `model: str`（LLM 模型，继承系统默认）、`hallucination_prompt_template: str`（幻觉检测提示词模板）、`block_threshold: float`（0-1，幻觉分数 >= 此值阻断管道，默认 0.8）、`max_retries: int`（LLM 调用重试次数，默认 2）、`detailed_mode: bool`（true=逐句分析，false=仅整体判断，默认 true） |
| **参数表单** | LLM 模型选择 + 阻断阈值滑动条 + 提示词模板文本区 + 最大重试次数 + 详细模式开关 |

### 3.7 引用验证 (`citation_verify`)

| 维度 | 说明 |
|------|------|
| **文件** | `nodes/quality/citation_verify.py` |
| **继承来源** | 新建。通过 LLM 调用实现，提示词要求验证答案中的每个引用声明是否能在检索上下文中找到支撑 |
| **输入类型** | `CitationInput`（字段：`answer: str`、`context_chunks: list[str]`、`citations: list[str]`—答案中声明的引用 ID 列表） |
| **输出类型** | `CitationReport`（字段：`verified_count: int`、`unverified_count: int`、`total_citations: int`、`verification_rate: float`、`details: list[CitationDetail]`，其中 `CitationDetail` 含 `citation_id: str`、`verified: bool`、`matched_context_index: int | None`、`explanation: str`） |
| **执行逻辑** | 1. 构建引用验证 prompt：注入答案文本 + 检索上下文 + 引用列表<br>2. 调用 LLM，要求输出每个引用的验证结果（是否能在上下文中找到支撑）<br>3. 使用 `json-repair` 修复格式<br>4. 统计验证通过率<br>5. 若 `verification_rate < min_rate`，标记 `passed=false`，可由下游节点或条件边决策 |
| **配置参数** | `model: str`（LLM 模型）、`citation_prompt_template: str`（验证提示词模板）、`min_verification_rate: float`（0-1，低于此率标记失败，默认 0.5）、`max_retries: int`（默认 2）、`require_exact_match: bool`（true=精确匹配引用文本，false=语义匹配，默认 false） |
| **参数表单** | LLM 模型选择 + 最低验证率滑动条 + 提示词模板文本区 + 精确匹配开关 + 最大重试次数 |

### 3.8 速率限制 (`rate_limiter`)

| 维度 | 说明 |
|------|------|
| **文件** | `nodes/performance/rate_limiter.py` |
| **继承来源** | 新建。纯 Python 实现，无外部依赖。参考标准令牌桶算法 |
| **输入类型** | `Any`（透传上游输出，不修改数据，仅在执行前检查/等待） |
| **输出类型** | `Any`（透传上游输出，附加 `metadata: {rate_limited: bool, wait_ms: int}`） |
| **执行逻辑** | 1. 从 `context.config` 读取算法和参数<br>2. 使用 Redis 或内存作为计数器后端（生产环境用 Redis 保证多实例一致性）<br>3. **令牌桶**：每秒向桶中添加 `refill_rate` 个令牌，桶容量 `burst_size`。请求到来时消耗 1 令牌，无令牌则等待或拒绝<br>4. **滑动窗口**：记录最近 `window_size_ms` 内的请求时间戳列表。新请求到来时清理过期时间戳，若剩余 >= `max_requests` 则等待或拒绝<br>5. **漏桶**：固定速率处理请求，超出速率的请求排队或丢弃<br>6. 若等待超时（`timeout_ms`），抛出 `NodeExecutionError`<br>7. 透传上游数据 + 附加 rate_limit 元数据 |
| **配置参数** | `algorithm: Literal["token_bucket", "sliding_window", "leaky_bucket"]`（默认 "token_bucket"）、`refill_rate: float`（令牌/秒，令牌桶使用，默认 10.0）、`burst_size: int`（桶容量，默认 20）、`window_size_ms: int`（滑动窗口大小，默认 1000）、`max_requests: int`（窗口内最大请求数，默认 10）、`timeout_ms: int`（等待超时，0=立即拒绝，默认 5000）、`backend: Literal["memory", "redis"]`（计数器后端，默认 "memory"） |
| **参数表单** | 算法下拉选择 + refill_rate/burst_size（令牌桶）或 window_size/max_requests（滑动窗口）的动态表单 + 超时输入 + 后端选择（内存/Redis） |

### 3.9 结构化输出 (`structured_output`)

| 维度 | 说明 |
|------|------|
| **文件** | `nodes/synthesis/structured_output.py` |
| **继承来源** | 新建。通过 LLM 调用实现格式转换 |
| **输入类型** | `str | dict`（上游生成的答案文本或中间结果） |
| **输出类型** | `StructuredOutput`（字段：`format: Literal["json", "markdown", "table"]`、`content: str`、`schema_version: str | None`—仅 JSON 模式使用） |
| **执行逻辑** | 1. 从 `context.config` 读取输出格式和 JSON Schema（如有）<br>2. 根据 format 选择处理路径：<br>   a. **json**：调用 LLM 将答案转换为符合指定 JSON Schema 的结构化数据，`json-repair` 兜底<br>   b. **markdown**：调用 LLM 将答案重新编排为 Markdown 格式（含标题层级、列表、表格）<br>   c. **table**：调用 LLM 将答案提取为 Markdown 表格<br>3. 校验 JSON 输出是否符合 schema（jsonschema 库做最终校验）<br>4. 返回 `StructuredOutput` |
| **配置参数** | `format: Literal["json", "markdown", "table"]`（默认 "json"）、`model: str`（LLM 模型）、`json_schema: dict | None`（仅 JSON 模式需要，JSON Schema 定义）、`format_prompt_template: str`（格式化提示词模板）、`include_metadata: bool`（是否在输出中附加元数据，默认 false）、`max_retries: int`（默认 2） |
| **参数表单** | 输出格式下拉（JSON/Markdown/表格）+ JSON Schema 编辑器（仅 JSON 模式显示，Monaco Editor）+ 提示词模板文本区 + 包含元数据开关 + 最大重试次数 |

### 3.10 多模态检索 (`multimodal_search`)

| 维度 | 说明 |
|------|------|
| **文件** | `nodes/retrieval/multimodal_search.py` |
| **继承来源** | 新建。依赖 Phase 2 实现的 `VectorStoreAdapter`（多模态向量存储）和 `EmbeddingEngine`（支持文本/图片/表格 embedding） |
| **输入类型** | `MultimodalQuery`（字段：`text_query: str | None`、`image_url: str | None`、`table_context: str | None`—图片和表格的文本描述或 URL） |
| **输出类型** | `FusedMultiModalResult`（字段：`text_results: list[CandidateChunk]`、`image_results: list[ImageChunk]`、`table_results: list[TableChunk]`、`fused: list[CandidateChunk]`—融合后的统一候选列表） |
| **执行逻辑** | 1. 从 `context.config` 读取模态配置：`enabled_modalities` 决定启用哪些模态<br>2. **文本检索**（enabled_modalities 含 "text"）：通过 `VectorStoreAdapter.search()` 检索文本 embedding<br>3. **图片检索**（enabled_modalities 含 "image"）：<br>   a. 如有 `image_url`，用 CLIP/OpenCLIP 生成图片 embedding<br>   b. 用图片 embedding 检索图片向量索引<br>   c. 返回相似图片的 `ImageChunk` 列表（含 url、caption、similarity）<br>4. **表格检索**（enabled_modalities 含 "table"）：<br>   a. 将 `table_context`（表格文本描述）编码为 embedding<br>   b. 检索表格向量索引<br>   c. 返回 `TableChunk` 列表<br>5. 模态融合：使用 weighted RRF 将各模态结果合并排序（权重由 `modal_weights` 配置控制）<br>6. 返回 `FusedMultiModalResult` |
| **配置参数** | `enabled_modalities: list[Literal["text", "image", "table"]]`（默认 ["text"]）、`modal_weights: dict[str, float]`（各模态权重，如 `{"text": 0.5, "image": 0.3, "table": 0.2}`）、`top_k_per_modal: int`（每模态检索数，默认 10）、`fusion_method: Literal["rrf", "weighted"]`（默认 "weighted"）、`rrf_k: int`（RRF 常数，默认 60） |
| **参数表单** | 模态多选（文本/图片/表格）+ 每模态 top_k 输入 + 各模态权重数字输入（总和自动校验 1.0）+ 融合方法下拉 + RRF k 值 |

### 3.11 复用策略总结

| 节点 | 继承来源 | 继承方式 | 改动点 |
|------|---------|---------|--------|
| `content_audit` | `backend/src/service/content_audit_service.py` | 继承 `ContentAuditService` 核心逻辑，封装为 `BaseNodeExecutor` | 去除 `settings.rag_config` 直接依赖，改为从 `context.config` 读取；审核结果统一为 `AuditResult` 结构 |
| `rerank` | `backend/src/core/reranker.py` | 继承 `create_reranker()` 工厂和 `DashScopeReranker`/`CrossEncoderReranker` 类 | 去除 `monitoring_service` 直接调用，转为通过 `context.trace_span` 记录指标；`NodeWithScore` 适配到 `CandidateChunk` |
| `dedup` | `backend/src/core/rag/dedup_engine.py` | 继承 `DedupEngine` 的精确去重和 MinHash 去重算法 | 去除 `hash_utils.content_hash` 耦合；输出格式化为 `DedupOutput`（含统计信息） |
| 其余 7 个 | 无 | 新建 | 参考 `backend` 中对应逻辑片段（如 `sensitive_filter` 参考 `_local_audit` 正则部分），但整体为全新实现 |

---

## 4. 测试策略

### 4.1 单元测试

**每节点执行器测试**（10 个 × 至少每个 4 个测试 = ~40 测试用例）：

- `test_validate_config_valid`：合法配置返回空错误列表
- `test_validate_config_invalid`：非法配置返回非空错误列表（如 `initial_k=-1`、`minhash_threshold=2.0`、`block_threshold=-0.5`、未知 `algorithm`、空的 `word_list`、不存在的 `detection_types` 等）
- `test_execute_with_mock_data`：Mock 依赖后验证输出结构和元数据
- `test_execute_error_handling`：模拟依赖（LLM API/向量存储）失败时正确降级

**各节点特有单元测试**：

| 节点 | 测试文件 | 关键用例 |
|------|---------|---------|
| `sensitive_filter` | `tests/nodes/security/test_sensitive_filter.py` | block 模式抛出 NodeExecutionError；redact 模式返回脱敏文本；partial/whole/regex 三种匹配模式正确 |
| `pii_mask` | `tests/nodes/security/test_pii_mask.py` | 手机号 13812345678→138****5678；身份证前6后4保留；邮箱 user@example.com→u***@e***.com；多种 PII 堆叠正确 |
| `content_audit` | `tests/nodes/security/test_content_audit.py` | 本地规则匹配返回 failed；LLM审核（Mock）返回 flags；外部API（Mock）超时降级；strict_mode vs 非严格模式 |
| `rerank` | `tests/nodes/quality/test_rerank.py` | DashScope provider 正常排序；local provider 正常排序；initial_k=0 返回空列表；scores 在 [0,1] 范围内 |
| `dedup` | `tests/nodes/quality/test_dedup.py` | 完全重复内容（相同hash）只保留1个；近似重复（MinHash 相似度>0.7）去重；空列表返回空；去重统计正确 |
| `hallucination_check` | `tests/nodes/quality/test_hallucination_check.py` | 完全 grounding 的答案 score<0.2；无上下文的答案 score>0.8；JSON 解析错误时 json-repair 兜底；score>=block_threshold 抛异常 |
| `citation_verify` | `tests/nodes/quality/test_citation_verify.py` | 全部引用可验证→rate=1.0；部分引用无支撑→rate<min_rate 标记失败；无引用→total_citations=0 |
| `rate_limiter` | `tests/nodes/performance/test_rate_limiter.py` | 令牌桶 burst 内快速请求通过；超出 burst 等待或拒绝；滑动窗口越界旧请求过期；timeout_ms=0 立即拒绝 |
| `structured_output` | `tests/nodes/synthesis/test_structured_output.py` | JSON 格式符合 schema；Markdown 格式含正确标题层级；Table 格式含 Markdown 表格语法；非法 JSON 被 json-repair 修复 |
| `multimodal_search` | `tests/nodes/retrieval/test_multimodal_search.py` | 仅文本模态=普通向量检索；多模态融合权重正确；禁用模态不查询对应索引；RRF vs weighted 融合结果差异 |

### 4.2 集成测试

**管道内集成**（使用测试知识库数据 + Mock LLM/VectorStore）：

- `test_sensitive_filter_in_pipeline`：敏感词过滤节点插入查询理解链后，block 模式阻断管道，redact 模式继续执行
- `test_rerank_after_retrieval`：检索→重排序链路完整执行，验证 results 数量 ≤ final_k，scores 更新
- `test_dedup_after_fusion`：多源检索→结果融合→去重链路，验证去重统计与下游节点接收的项数一致
- `test_hallucination_check_in_answer_chain`：检索→LLM 生成→幻觉检测链路，验证幻觉检测阻断逻辑正确
- `test_rate_limiter_with_concurrent_requests`：并发请求超过速率限制，验证部分请求等待/拒绝，无崩溃
- `test_structured_output_format_chain`：检索→生成→结构化输出链路，验证最终输出为指定格式

**完整管道编译 + 执行**：

- `test_compile_pipeline_with_all_phase8_nodes`：管道配置包含全部 10 种 Phase 8 节点，编译通过
- `test_execute_full_pipeline_with_quality_nodes`：包含 rerank→dedup→hallucination_check→citation_verify 的质量管道完整执行

### 4.3 关键测试场景（≥8 个）

| # | 场景 | 验证点 |
|---|------|--------|
| 1 | 查询含敏感词，sensitive_filter 设 block 模式 | 管道执行中断，NodeExecutionError 含匹配词详情 |
| 2 | 查询含敏感词，sensitive_filter 设 redact 模式 | 管道继续，脱敏文本传给下游，has_issues=true |
| 3 | 用户输入含手机号和身份证，pii_mask 完整脱敏 | 输出 masked 字段正确改写，detected_items 含两个 PII 项 |
| 4 | 检索 50 候选→rerank→final_k=5 返回 | 输出仅为 5 个结果，scores 更新为 rerank 分数 |
| 5 | 检索结果含 3 条完全相同内容+2 条近似内容→dedup | exact_dedup_count=2，minhash_dedup_count≥1，total_removed≥3 |
| 6 | LLM 生成的答案与检索上下文完全无关→hallucination_check | hallucination_score≥0.8，block_threshold=0.8 触发阻断 |
| 7 | 答案含 5 个引用，其中 2 个在上下文中找不到→citation_verify | verification_rate=0.6，min_rate=0.7→标记 failed |
| 8 | 10 个并发请求，rate_limiter 设 max_requests=5 | 前 5 个通过，后 5 个等待或返回限流拒绝 |
| 9 | structured_output format=json+schema，LLM 输出合法 JSON | 输出通过 jsonschema 校验，content 为合法 JSON 字符串 |
| 10 | multimodal_search 同时启用 text+image，只有文本查询 | 仅 text_results 非空，image_results=[]，融合权重自动归一化 |
| 11 | content_audit 严格模式，LLM 审核返回 1 个 critical flag | passed=false，管道中断，reason 含 flag 详情 |
| 12 | dedup 空输入列表 | 返回空 DedupOutput，exact_dedup_count=0，minhash_dedup_count=0 |

---

## 5. 验收检查点

### 5.1 节点注册与发现

- [ ] 全部 10 种节点类型在 `NodeRegistry` 中注册成功（调用 `NodeRegistry.list_types()` 包含全部 10 个类型名）
- [ ] 管道编辑器节点面板左侧出现 5 个新分组（安全合规/质量增强/性能优化/答案合成/多模态检索），含 10 种可拖拽节点
- [ ] `kahn_sort` 支持包含这些新节点的管道拓扑排序（线性链、菱形、复杂图）

### 5.2 配置校验

- [ ] 每个 `validate_config()` 覆盖边界值：参数范围越界返回非空错误列表
- [ ] 必填参数缺失时返回明确错误（如 `structured_output.format=="json"` 但 `json_schema==None`）
- [ ] 参数类型错误返回可读消息（如 `initial_k` 传字符串 "abc"）
- [ ] 空配置（`config={}`）不崩溃，使用 `NODE_DEFAULTS` 兜底

### 5.3 执行正确性

- [ ] 每个节点 `execute(context)` 在有合法输入时返回 `NodeResult(output=..., metadata=..., degraded=False)`
- [ ] 每个节点 `execute(context)` 在输入不合法或依赖失败时正确抛 `NodeExecutionError` 或触发降级
- [ ] 透传节点（`rate_limiter`）不修改数据内容，仅附加 metadata
- [ ] LLM 调用类节点（`content_audit`, `hallucination_check`, `citation_verify`, `structured_output`）在 LLM 不可用时降级

### 5.4 降级链兼容

- [ ] 每个节点失败时按 `skip_node → reroute → degrade_cache → abort` 降级链顺序执行
- [ ] `sensitive_filter` 降级时（block 模式但降级配置为 skip_node）原查询直传下游
- [ ] `rerank` 降级时直传前 `final_k` 个原始候选
- [ ] LLM 类节点降级时返回保守默认值（如 `hallucination_check` 降级返回 `is_hallucinated=false`）
- [ ] `rate_limiter` 降级时跳过限流检查，直传数据

### 5.5 参数表单

- [ ] 全部 10 个前端参数表单组件可正常渲染
- [ ] 表单修改通过 `onChange` 正确更新节点 `config`
- [ ] 表单校验与后端 `validate_config()` 规则一致（前后端双重校验）
- [ ] 条件字段联动正确（如 `structured_output.format` 切换时显示/隐藏 `json_schema` 编辑器）
- [ ] 数字输入控件限制范围（如 `minhash_threshold` 在 0-1 之间）

### 5.6 追踪集成

- [ ] 每个节点执行产生一个 Span，包含 `node_id`、`node_type`、`domain_id`、`duration_ms`
- [ ] `rerank` 节点 Span 记录 `reranker_input_count`、`reranker_output_count`
- [ ] `dedup` 节点 Span 记录 `exact_dedup_count`、`minhash_dedup_count`、`total_removed`
- [ ] 降级事件在 Span 中标记 `degraded=true` + `degradation_strategy`
- [ ] `rate_limiter` 节点 Span 记录 `wait_ms`、`rejected` 标记

### 5.7 代码质量

- [ ] 所有实体类在 `schemas/pipeline/` 或 `schemas/node_io/` 下定义，无 controller/service/core 中定义 BaseModel
- [ ] 单类 ≤ 500 行
- [ ] 所有业务异常继承 `AppException`
- [ ] 全中文注释
- [ ] 复用类（`DedupEngine`、`create_reranker`、`ContentAuditService`）的接口改造后仍可正常 import 使用
- [ ] 所有 LLM 调用使用 `json-repair` 兜底
- [ ] 敏感配置（`external_api_key`、`external_api_url`）不写入日志

### 5.8 向后兼容

- [ ] 已完成的 Phase 3 管道（仅含检索+聚合节点）不受新节点影响
- [ ] 管道编辑器中已实现的 18 个节点参数表单正常
- [ ] 管道编译不因新增节点类型而破坏已有单元测试

---

## 6. 配套文件清单

Phase 8 预计新建文件约 23 个：

| 类别 | 文件数 | 文件 |
|------|--------|------|
| 节点执行器 | 12 | `nodes/security/__init__.py`, `sensitive_filter.py`, `pii_mask.py`, `content_audit.py`；`nodes/quality/__init__.py`, `rerank.py`, `dedup.py`, `hallucination_check.py`, `citation_verify.py`；`nodes/synthesis/__init__.py`, `structured_output.py`；`nodes/retrieval/multimodal_search.py` |
| 前端参数表单 | 10 | `PropertyPanel/forms/SensitiveFilterParameterForm.tsx` 等 10 个 |
| 测试文件 | 10 | `tests/nodes/security/test_sensitive_filter.py`, `tests/nodes/quality/test_rerank.py` 等 |
| 修改文件 | 5 | `core/pipeline/__init__.py`（注册新节点）、`core/pipeline/defaults.py`（L0 默认值）、`PropertyPanel.tsx`（追加表单映射）、`NodePanel.tsx`（追加可拖拽节点）、`schemas/node_io/__init__.py`（输入输出类型定义） |

**总计**：约 37 个文件（含改造文件）

---

## 7. 与其他阶段的接口

| 接口方向 | 阶段 | 依赖内容 |
|---------|------|---------|
| **输入** | Phase 0 | 基础设施：`api/json_response.py`、`middleware/exception_handler.py`、`core/tracing/`、`core/llm/`、`core/config/` |
| **输入** | Phase 2 | 知识库：`VectorStoreAdapter`（multimodal_search 多模态检索依赖） |
| **输入** | Phase 3 | 管道引擎：`BaseNodeExecutor`、`NodeContext`、`NodeResult`、`NodeRegistry`、`PipelineCompiler` |
| **输出** | Phase 5 | 管道编辑器前端：10 个参数表单组件嵌入 `PropertyPanel` + 10 个可拖拽节点加入 `NodePanel` |
| **输出** | Phase 4 | 搜索 API：管道执行时可能调用这些节点（如限流、结构化输出），无需额外改动 |

---

## 8. 变更历史

| 日期 | 变更 |
|------|------|
| 2026-05-14 | 初始创建：基于 implementation-checklist.md Phase 8 任务清单 + implementation-plan-detail.md §1.8 节点清单 |
