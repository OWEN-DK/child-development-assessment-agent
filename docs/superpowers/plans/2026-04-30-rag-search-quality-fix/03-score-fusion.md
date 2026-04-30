# 03 P1：重写分数融合体系

> 这是搜索质量差的根本原因。分数体系修好后，"评分区分度低"和"结果来源单一"的问题应同步解决。
> 依赖 P0 完成后才能完整测试。P0-3（PageIndex 增强）暂缓，不影响核心融合链路。

---

## 背景核实

代码中存在两条独立的融合路径，行为不同：

| 方法 | 调用方 | 归一化 | 惩罚逻辑 | 默认权重 |
|------|--------|--------|---------|---------|
| `merge_results()` | `KnowledgeRetriever`（非 pipeline）+ `HybridRetrievalStep`（pipeline） | 有 `_normalize_all_scores`（实际 no-op） | 无 | BM25 0.5 / Vector 0.5 |
| `merge_for_search()` | `RetrievalFacade.search_content()`（搜索页） | 无 | `no_match_vector_penalty`（0.3） | BM25 0.7 / Vector 0.3 |

下游分数消费者：

| 消费方 | 文件:行 | 阈值 | 预期分数范围 |
|--------|---------|------|------------|
| `_convert_to_knowledge_items` | knowledge_retriever.py:168 | `rag_search_min_similarity_threshold` (0.2) | 0.2~1.0 |
| `_process_search_results` | result_processor.py:98,170 | `rag_search_score_threshold_hybrid` (0.25) | 加权原始分，可能很低 |
| 分数显示映射 | result_processor.py:200-222 | `[threshold, 0.65]` → `[0.55, 0.98]` | 依赖旧范围 |

---

## P1-1 实现 RRF 替换加权线性求和（问题 1 + 5）

### 核实事实

- `hybrid_retrieval.py` 无 RRF 实现，只有加权线性融合
- `rag_pipeline.yaml` 声明 `fusion_mode: "reciprocal_rank"` 但无代码读取
- `_normalize_all_scores()` 是 no-op（L84-89 两个分支都返回原始值）
- `_calibrate_vector_score()` 用任意乘数（0.95/0.7）引入偏差
- `_calibrate_bm25_score()` sigmoid 压缩丢失排序信息

### 修复

**Step 1**：新增 `merge_rrf()` 静态方法

```python
@staticmethod
def merge_rrf(
    bm25_nodes: List[NodeWithScore],
    vector_nodes: List[NodeWithScore],
    k: int = 60,
    limit: int = 10,
) -> List[NodeWithScore]:
    """Reciprocal Rank Fusion — 基于排名融合，无需分数归一化"""
    node_map: Dict[str, NodeWithScore] = {}
    rrf_scores: Dict[str, float] = {}

    # BM25 排名贡献
    sorted_bm25 = sorted(bm25_nodes, key=lambda n: n.score or 0, reverse=True)
    for rank, node in enumerate(sorted_bm25):
        nid = node.node_id or id(node)
        node_map[nid] = node
        rrf_scores[nid] = rrf_scores.get(nid, 0.0) + 1.0 / (k + rank + 1)

    # 向量排名贡献
    sorted_vector = sorted(vector_nodes, key=lambda n: n.score or 0, reverse=True)
    for rank, node in enumerate(sorted_vector):
        nid = node.node_id or id(node)
        if nid in node_map:
            node_map[nid] = node
        else:
            node_map[nid] = node
        rrf_scores[nid] = rrf_scores.get(nid, 0.0) + 1.0 / (k + rank + 1)

    # 排序并赋分
    ranked = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)
    results = []
    for nid, score in ranked[:limit]:
        node = node_map[nid]
        node.score = score
        results.append(node)
    return results
```

**Step 2**：删除废弃方法

- `_calibrate_bm25_score()` — 删除
- `_normalize_all_scores()` — 删除
- `_calibrate_vector_score()` — 删除

**Step 3**：`merge_results()` 内部改为调用 `merge_rrf()`

保留 `merge_results()` 签名以兼容调用方，内部改为：
```python
@staticmethod
def merge_results(bm25_nodes, vector_nodes, bm25_weight=0.5, vector_weight=0.5,
                  merge_mode="OR", limit=10, normalize_scores=True) -> List[NodeWithScore]:
    return HybridRetrievalMerger.merge_rrf(bm25_nodes, vector_nodes, limit=limit)
```

参数 `bm25_weight`/`vector_weight`/`merge_mode`/`normalize_scores` 不再使用但保留签名，避免调用方报错。后续阶段（P2）统一清理。

**Step 4**：`merge_for_search()` 同样改为 RRF

```python
@staticmethod
def merge_for_search(bm25_nodes, vector_nodes, bm25_weight=0.7, vector_weight=0.3,
                     no_match_vector_penalty=0.3, limit=20) -> List[NodeWithScore]:
    return HybridRetrievalMerger.merge_rrf(bm25_nodes, vector_nodes, limit=limit)
```

`no_match_vector_penalty` 不再需要——RRF 天然对单源节点给予较低分数（只有一半排名贡献）。

**Step 5**：`HybridRetrievalStep` 读取 `fusion_mode` 配置

```python
fusion_mode = self.config.get("fusion_mode", "weighted_sum")
if fusion_mode == "reciprocal_rank":
    return HybridRetrievalMerger.merge_rrf(bm25, vector, limit=...)
else:
    return HybridRetrievalMerger.merge_results(...)
```

### RRF 优势

- 只看排名，不看分数绝对值 → 天然消除 BM25/向量/Cross-Encoder 的尺度差异
- 不需要权重调参（`k=60` 是论文标准值）
- 不需要归一化、校准等后处理

### 阈值重校准

RRF 分数范围与旧的加权分数完全不同。RRF 分数 = `sum(1/(k+rank+1))`，双源命中的最高分约为 `2/(k+1) ≈ 0.033`，单源最高约 `0.016`。

**必须同步调整的配置**：

| 配置项 | 旧值 | 说明 |
|--------|------|------|
| `rag_search_min_similarity_threshold` | 0.2 | 用于 knowledge retriever，需大幅降低（约 0.005） |
| `rag_search_score_threshold_hybrid` | 0.25 | 用于 search result processor，需大幅降低（约 0.005） |
| `rag_search_score_threshold_vector` | 0.25 | 同上 |
| `rag_scoring_max_expected_score` | 0.65 | 分数显示映射上限，需调整为 RRF 最高分（约 0.033） |

**具体校准方法**：
1. 改完 RRF 后，用 10 条典型查询跑检索，记录分数分布
2. 用 P95 分位数作为阈值上限，P5 作为下限
3. 更新配置值

### 验证

- [ ] 搜索"自闭症儿童的社交训练方法"返回多源结果（不再只来自一本书）
- [ ] 搜索"感觉统合"BM25 + 向量混合结果均被保留
- [ ] 相同查询的分数有明确区分度（不再集中在 0.4-0.6）
- [ ] 单源向量结果不再被双重惩罚过滤

---

## P1-2 消除向量惩罚（问题 2 + 17）

### 核实事实

`merge_for_search()` 中纯向量结果经过：
- `effective_vector_weight = 0.3`（BM25 存在时）
- `no_match_vector_penalty = 0.3`
- 最终有效权重 = 0.09

L302 `vector_penalty = 1.0 if bm25_nodes else 1.0` 是死代码。

### 修复

P1-1 中已将 `merge_for_search()` 改为 RRF，惩罚逻辑自然消除。

额外清理：
- 删除 `no_match_vector_penalty` 参数
- 删除 L302 死代码
- 删除 `effective_vector_weight` 逻辑

### 验证

- [ ] "自闭症儿童的社交训练方法"（BM25 可能无精确命中）返回向量检索结果
- [ ] 向量独有结果分数与双源结果可比较（RRF 下差距约 2x，非 10x）

---

## P1-3 Reranker logits 归一化（问题 12）

**文件**：`backend/src/core/reranker.py`

### 核实事实

`CrossEncoder.predict()` 返回 raw logits（`bge-reranker-v2-m3` 典型范围 -10 到 +10）。
L142-143 直接赋给 `node.score`，无 sigmoid。
L168 的"改善率"比较 logits（-10~+10）与融合分数（0~1），无意义。

### 修复

```python
import math

# L142-143 修改
for node, score in zip(nodes, scores):
    node.score = 1.0 / (1.0 + math.exp(-float(score)))  # sigmoid → (0, 1)
```

### 验证

- [ ] reranker 输出的 `node.score` 在 (0, 1) 范围
- [ ] "改善率"数值在合理范围（0%~200% 而非 488%）

---

## P1-4 删除分数校准边界不连续（问题 18）

### 修复

P1-1 中已删除 `_calibrate_vector_score()`，0.7 和 0.5 处的阶跃自动消除。

### 验证

- [ ] `grep "_calibrate_vector_score" backend/src/core/hybrid_retrieval.py` 返回空

---

## P1-5 YAML 配置与实现对齐（问题 5）

### 核实事实

YAML 中有两个死配置：
1. `fusion_mode: "reciprocal_rank"` — P1-1 实现后变为真实
2. `vector_weight: 0.5` — `HybridRetrievalStep` 算 `1-bm25_weight`，永远不读此值

### 修复

P1-1 Step 5 已让 `HybridRetrievalStep` 读取 `fusion_mode`。

额外清理 YAML：删除 `vector_weight` 行（避免误导），或改为注释说明 `vector_weight` 由代码自动计算。

### 验证

- [ ] YAML 中 `fusion_mode` 被 `HybridRetrievalStep` 实际读取
- [ ] YAML 中 `vector_weight` 标注为自动计算或删除
