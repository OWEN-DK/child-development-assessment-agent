# RAG 检索质量诊断：分数归一化 + 同义词验证

> 日期：2026-04-30
> 状态：调研完成，待实施

## 1. 问题描述

内容搜索页面所有检索结果的相关度分数均显示 **98.0%**，无任何区分度。

## 2. 根因分析

### 2.1 当前分数映射机制

当前实现位于 `backend/src/service/retrieval/result_processor.py`（约 L200-220），采用**固定阈值线性映射**：

```
内部 RRF 分数 → [threshold, max_expected_score] → [base_display_score, max_display_score]
```

配置默认值（`backend/src/config/modules/rag/core.py`）：

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `max_expected_score` | 0.03 | 预期 RRF 最高分 |
| `base_display_score` | 0.55 | 展示最低分 |
| `max_display_score` | 0.98 | 展示最高分 |

### 2.2 Bug 机制

RRF 公式：`score = Σ 1/(k + rank + 1)`，其中 `k=60`。

双源命中（BM25 + 向量同时返回同一文档）时：
- rank-1 双源得分 = `2/(60+1)` = **0.0328**
- 超过了 `max_expected_score` 的 0.03

代码中的截断逻辑：

```python
if final_score >= max_expected_score:
    display_score = max_display_score  # 直接赋 0.98
```

几乎所有有效结果（双源命中的高质量结果）都会触发此分支，统一显示为 98.0%。

### 2.3 单源命中的情况

单源 rank-1 得分 = `1/(60+1)` = 0.0164，低于 0.03 但高于 threshold（0.025），会被线性映射到 55%-98% 之间的某个值——但这类结果通常在排序中靠后，用户看到的大多数是双源命中结果。

## 3. 行业实践调研

### 3.1 Elasticsearch

- RRF 作为 `rank_constant` 参数（等价于 k），默认值 100
- **不返回归一化分数**：RRF 原始分数直接返回，文档明确说明 RRF 分数不可跨查询比较
- 用户若需展示百分比，需自行在客户端做归一化
- 文档地址：https://www.elastic.co/guide/en/elasticsearch/reference/current/rrf.html

### 3.2 Azure AI Search

- 同样支持 RRF 融合
- 文档明确指出：**RRF 分数范围由融合的查询数量决定**（双源时上限为 2/k+1）
- 不提供内置的百分比映射，原始分数仅供排序使用
- 文档地址：https://learn.microsoft.com/en-us/azure/search/hybrid-search-ranking

### 3.3 OpenSearch

- 最完善的归一化方案，提供三种技术：
  1. **min-max 归一化**：将每个查询的结果分数映射到 [0, 1]
  2. **L2 归一化**：除以 L2 范数
  3. **z-score 归一化**：基于均值和标准差
- 推荐在混合搜索中使用 **min-max** 作为首选方案
- 归一化在 RRF 融合**之前**对每个检索器的分数分别进行
- 文档地址：https://opensearch.org/docs/latest/search-plugins/hybrid-search/

### 3.4 行业共识

| 实践 | 说明 |
|------|------|
| RRF 分数不做百分比映射 | 主流搜索引擎（ES、Azure）认为 RRF 分数仅用于排序，不具备绝对含义 |
| 需要展示时用 per-query 归一化 | 在当前查询结果集内做 min-max，而非固定阈值 |
| 归一化时机 | 融合前（对每个检索器单独归一化）或融合后（对最终结果归一化）均可 |

## 4. 推荐方案：Per-Query Min-Max 归一化

### 4.1 核心思路

不再使用固定的 `max_expected_score` 做阈值映射，改为**对当前查询的结果集动态计算 min/max**：

```python
# 1. 收集所有通过阈值过滤的结果的原始分数
raw_scores = [r.raw_score for r in results]

# 2. 计算 per-query 的 min/max
score_min = min(raw_scores)
score_max = max(raw_scores)

# 3. 映射到展示范围
if score_max > score_min:
    normalized = (raw_score - score_min) / (score_max - score_min)
    display_score = base_display + normalized * (max_display - base_display)
else:
    display_score = (base_display + max_display) / 2  # 单结果时取中值
```

### 4.2 优势

- **结果集内自洽**：同一查询内分数有区分度
- **无固定阈值依赖**：不依赖 `max_expected_score` 的准确估计
- **实现简单**：改动集中在 `result_processor.py` 的分数映射段

### 4.3 注意事项

- 跨查询的分数不可比（这是 RRF 的固有特性，行业也接受此限制）
- 单结果时特殊处理，避免除零
- 极端情况（所有结果分数相同）需 fallback

## 5. 影响范围

| 文件 | 改动 |
|------|------|
| `backend/src/service/retrieval/result_processor.py` | 分数映射逻辑重写 |
| `backend/src/config/modules/rag/core.py` | 移除 `max_expected_score`，保留 `base/max_display_score` |
| `backend/config/rag_pipeline.yaml` | 同步移除对应配置项 |

前端无需改动，展示逻辑 `{(item.score * 100).toFixed(1)}%` 保持不变。

---

# 二、SynonymValidator 同义词误杀问题

## 1. 问题描述

`SynonymValidator._has_semantic_overlap` 使用 jieba 分词交集判断两个词是否"语义重叠"。导致真正的同义词（如"孩子"↔"儿童"、"幼儿"）被全部拒绝——因为同义词的定义就是词汇不同但语义相同，分词交集永远为空。

**影响**：同义词扩展功能实质失效。当前能通过验证的词全靠 `synonym_validation.json` 的 whitelist/domain_terms 硬编码规则兜底，LLM 生成的任何未预设同义词全部被误杀。

## 2. 根因分析

### 2.1 当前逻辑

```
synonym_validator.py L139-155:

_has_semantic_overlap(term, original_query):
    term_words = jieba.lcut(term)      → {"孩子"}
    query_words = jieba.lcut(original_query) → {"儿童"}
    term_words & query_words           → {} (空集)
    return False                       → 拒绝
```

### 2.2 为什么是根本性缺陷

| 原词 | 同义词 | 分词结果 | 交集 | 判定 |
|------|--------|----------|------|------|
| 儿童 | 孩子 | {"儿童"} ∩ {"孩子"} | ∅ | 拒绝 |
| 注意力 | 专注力 | {"注意力"} ∩ {"专注力"} | ∅ | 拒绝 |
| 感统 | 感觉统合 | {"感统"} ∩ {"感觉","统合"} | ∅ | 拒绝 |

同义词的定义就是"词汇不同、语义相同"，用词汇交集去检测语义重叠，逻辑上矛盾。

### 2.3 当前的"保底"机制

`_check_term` 的检查顺序（synonym_validator.py L92-120）：

1. 长度检查 → 拒绝太短/太长的词
2. 黑名单 → 拒绝不相关领域词
3. 太宽泛检查 → 拒绝粒度不够的词
4. **白名单** → 通过（domain_whitelist）
5. **domain_terms valid 列表** → 通过（硬编码规则）
6. **`_has_semantic_overlap`** → ❌ 真正的同义词在此被全部拒绝

只有被写进 JSON 规则文件的词能通过第 4/5 步提前返回，绕过第 6 步。LLM 生成的任何新同义词都会撞上第 6 步。

## 3. 方案：Embedding 余弦相似度替换分词交集

### 3.1 核心思路

用已有的 `EmbeddingHelper` + `cosine_similarity` 替换 jieba 分词交集。项目内已有 5 处使用相同模式做语义比较（`faithfulness_checker`、`answer_relevancy_calc` 等），无新依赖。

### 3.2 设计

```python
async def validate(self, synonym_list, original_query):
    # 1. 批量 embed 所有 term + original_query（一次 API 调用）
    all_texts = list(set(synonym_list + [original_query]))
    embeddings = await self._embedding_helper.embed_batch(all_texts)
    embedding_map = dict(zip(all_texts, embeddings))

    # 2. 逐个检查（传入预计算的 embedding）
    for term in synonym_list:
        reason = self._check_term(term, original_query, embedding_map)
        ...

def _has_semantic_overlap(self, term, original_query, embedding_map):
    # 快速路径：jieba 分词有交集 → 直接通过（保留，分词重叠确实意味语义重叠）
    if jieba_token_overlap(term, original_query):
        return True

    # 语义路径：余弦相似度 >= threshold
    term_emb = embedding_map.get(term)
    query_emb = embedding_map.get(original_query)
    if term_emb and query_emb:
        similarity = cosine_similarity(term_emb, query_emb)
        return similarity >= self._similarity_threshold

    # 降级：embedding 不可用时 fail-open，避免误杀
    return True
```

### 3.3 关键设计决策

| 决策 | 理由 |
|------|------|
| `validate()` 改为 async | `EmbeddingHelper.embed_batch` 是异步 API |
| 批量 embed 后传入 `_check_term` | 避免逐词调用 API，一次调用搞定 |
| 保留 jieba 快速路径 | 分词有交集 = 一定语义相关，无需调 API |
| fail-open 降级 | DashScope 不可用时宁可放过，不可误杀 |
| 新增 `rag_synonym_similarity_threshold` 配置项 | 默认 0.5，可调优 |

### 3.4 预期效果

| 原词 | 同义词 | 当前结果 | 修复后 |
|------|--------|----------|--------|
| 儿童 | 孩子 | 拒绝 | 通过（cos ≈ 0.8+） |
| 注意力 | 专注力 | 通过（whitelist） | 通过（cos ≈ 0.7+） |
| 注意力 | 视力 | 通过（blacklist） | 拒绝（blacklist 优先级更高） |
| 注意力 | 数学能力 | 拒绝 | 拒绝（cos ≈ 0.3） |
| 感统 | 感觉整合 | 通过（domain_terms） | 通过（cos ≈ 0.7+） |

## 4. 影响范围

| 文件 | 改动 |
|------|------|
| `backend/src/core/rag/synonym_validator.py` | 核心逻辑重写 |
| `backend/src/service/retrieval/query_rewriter.py` | 适配 async（validate 调用点加 await） |
| `backend/src/config/modules/rag/retrieval.py` | 新增 `rag_synonym_similarity_threshold` |
| `backend/config/rag_pipeline.yaml` | 同步新增配置项 |
| `backend/tests/test_synonym_validator.py` | 适配 async + 新增用例 |

### query_rewriter.py 改动细节

- `_expand_synonyms`（async）中 `validate()` 调用加 `await`
- `_local_expand_synonyms`（sync）改为 `async def`，调用点加 `await`
- `_expand_synonyms` 中调用 `_local_expand_synonyms` 的 3 处加 `await`

### 测试新增用例

- 真正同义词（如"孩子"↔"儿童"）能通过
- 无关词（如"注意力" vs "数学能力"）仍被拒绝
- embedding 不可用时 fail-open

## 5. 验证

1. `cd backend && uv run pytest tests/test_synonym_validator.py -v` — 全部通过
2. 启动后端，搜索"孩子"或"幼儿"，观察同义词扩展日志不再全部拒绝
3. 确认已有功能不退化：黑名单、白名单、粒度控制、长度检查等规则仍然生效
