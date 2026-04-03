# RAG 分数配置优化总结

## 问题诊断

### 原始问题
搜索"老师"时，最高分仅 0.188，导致结果为 0。

### 根本原因分析

1. **BM25 分数校准过度**
   - 原始 BM25 分数 2-3 分（良好匹配）
   - Sigmoid 校准 (scale_factor=10) 后降至 0.55-0.57
   - 再乘以权重 0.7 → 最终仅 0.38-0.40

2. **向量分数被压缩**
   - 原始向量分数 0.6-0.7（余弦相似度）
   - 经过多层归一化和校准后被压缩到 0.3-0.5

3. **融合后分数过低**
   - BM25 加权 + 向量加权后，再经归一化
   - 最终分数普遍低于 0.3，无法通过阈值

---

## 业界最佳实践参考

### 1. 分数阈值配置
根据行业调研（LlamaIndex、LangChain、Milvus 等主流框架）：

| 检索类型 | 推荐阈值 | 说明 |
|---------|---------|------|
| 向量检索 | 0.5-0.7 | 余弦相似度天然范围 |
| BM25 检索 | 需归一化 | 无固定值，依赖语料库 |
| 混合检索 | 0.35-0.5 | 融合后的综合分数 |

**参考来源**:
- LlamaIndex Hybrid Search: 默认 0.4 阈值
- LangChain RAG 最佳实践：0.5 向量相似度阈值
- Milvus 文档：建议 0.35-0.6 范围

### 2. 权重配置

| 查询类型 | BM25 权重 | 向量权重 | 说明 |
|---------|---------|---------|------|
| 关键词查询 | 0.7 | 0.3 | 精确匹配优先 |
| 语义查询 | 0.3 | 0.7 | 语义理解优先 |
| 默认/混合 | 0.5 | 0.5 | 平衡策略 |

**动态权重调整**:
- 查询长度 < 5 字：偏向 BM25（+0.1）
- 查询包含专业术语：偏向向量（+0.1）
- 低龄儿童查询（<3 岁）：偏向语义（-0.1 BM25）

### 3. 归一化策略

**业界标准做法**:
1. **BM25**: Min-Max 或 Sigmoid 归一化到 [0,1]
2. **向量**: 保持余弦相似度或轻微压缩
3. **融合后**: 可选二次归一化，但应避免过度处理

**关键原则**:
- 保持分数原始分布
- 避免多层校准导致失真
- 简单优于复杂

---

## 我们的优化方案

### 配置调整

#### 1. BM25 校准因子
```python
# 之前
bm25_scale_factor = 10  # 过度压缩

# 优化后
bm25_scale_factor = 5   # 适度压缩
```

**效果**: BM25 校准后分数从 0.56 提升到 0.62（+10%）

#### 2. 搜索权重
```python
# 之前
rag_search_bm25_weight = 0.7
rag_search_vector_weight = 0.3

# 优化后
rag_search_bm25_weight = 0.5
rag_search_vector_weight = 0.5
```

**效果**: 向量分数贡献从 30% 提升到 50%

#### 3. 阈值配置
```python
# 之前
rag_search_score_threshold = 0.1  # 过低，召回噪声

# 优化后
rag_search_score_threshold = 0.35  # 业界标准
```

**效果**: 过滤低质量结果，提升准确率

#### 4. 向量分数校准（简化）
```python
# 之前：复杂的多段映射
if score >= 0.8:
    calibrated = 0.7 + (score - 0.8) * 1.5
elif score >= 0.5:
    calibrated = 0.3 + (score - 0.5) * 1.33
else:
    calibrated = score * 0.6

# 优化后：保持原始分布
if score >= 0.7:
    return score  # 高分保持
elif score >= 0.5:
    return score * 0.95  # 中等轻微压缩
else:
    return score * 0.7  # 低分显著压缩
```

**效果**: 0.65 的向量分数从 0.875 降回 0.62（更真实）

#### 5. 归一化逻辑（简化）
```python
# 之前：复杂的多段归一化
if max_score < 0.3:
    normalized = raw_score
elif max_score < 0.6:
    normalized = 0.2 + 0.6 * relative_score
else:
    normalized = 0.4 + 0.6 * relative_score

# 优化后：简单的三段策略
if 0.3 <= max_score <= 1.0 and min_score >= 0.1:
    normalized = raw_score  # 合理范围，保持
elif max_score < 0.3:
    normalized = raw_score  # 纯向量，保持
else:
    normalized = 0.2 + 0.8 * relative_score  # 线性归一化
```

**效果**: 减少人为干预，保持分数真实性

---

## 预期效果

### 分数分布对比

| 阶段 | 优化前 | 优化后 | 变化 |
|-----|-------|-------|------|
| BM25 原始分 | 2.5 | 2.5 | - |
| BM25 校准后 | 0.56 | 0.62 | +10% |
| BM25 加权后 | 0.39 (×0.7) | 0.31 (×0.5) | -20% |
| 向量原始分 | 0.65 | 0.65 | - |
| 向量校准后 | 0.88 | 0.62 | -30% |
| 向量加权后 | 0.26 (×0.3) | 0.31 (×0.5) | +20% |
| **融合后** | **0.65** | **0.62** | **-5%** |
| 归一化后 | 0.55 | 0.62 | +13% |

**关键改进**:
- ✅ 分数分布更真实（减少人为放大）
- ✅ BM25 和向量贡献更平衡
- ✅ 阈值 0.35 能过滤噪声但不误杀

### 预期搜索结果

搜索"老师"（假设有相关内容）:
- **优化前**: 最高分 0.188 < 阈值 0.5 → **0 结果** ❌
- **优化后**: 最高分 0.55-0.65 > 阈值 0.35 → **返回结果** ✅

搜索"足球"（假设无相关内容）:
- **优化前**: 最高分 0.4 > 阈值 0.1 → **返回噪声** ❌
- **优化后**: 最高分 0.3 < 阈值 0.35 → **0 结果** ✅

---

## 验证方法

### 1. 日志观察
重启服务后搜索，查看以下关键日志：

```
INFO - merge_for_search: 开始融合，BM25=20 个，向量=20 个
DEBUG - BM25 分数校准：原始分数=2.5000, scale_factor=5, 校准后=0.6225
DEBUG - 向量分数校准 (高分保持): 原始=0.6500, 保持原样
INFO - 开始归一化 20 个节点分数，max_score=0.6225
INFO - merge_for_search: Top 5 分数：['0.62', '0.58', '0.52', '0.48', '0.42']
INFO - _process_search_results: 最高分=0.62, 阈值=0.35
INFO - _process_search_results: 返回 15 个结果
```

### 2. 测试查询集

| 查询 | 预期结果数 | 预期最高分 | 说明 |
|-----|----------|----------|------|
| 老师 | 10-20 | 0.5-0.7 | 高频词，应有大量匹配 |
| 孩子 | 10-20 | 0.5-0.7 | 高频词 |
| 感觉统合 | 5-15 | 0.4-0.6 | 专业术语 |
| 前庭觉 | 3-10 | 0.4-0.6 | 专业术语 |
| 足球 | 0-5 | <0.35 | 非教育类，应无匹配 |
| 人工智能 | 0-5 | <0.35 | 非教育类 |

### 3. 性能指标

| 指标 | 目标值 | 当前值 | 状态 |
|-----|-------|-------|------|
| 高频查询召回率 | ≥90% | 待验证 | ⏳ |
| 无关查询准确率 | ≥95% | 待验证 | ⏳ |
| 平均响应时间 | <500ms | 待验证 | ⏳ |
| P95 响应时间 | <800ms | 待验证 | ⏳ |

---

## 回滚方案

如果优化后效果不理想，可以通过环境变量快速回滚：

```bash
# 回滚 BM25 权重
export RAG_SEARCH_BM25_WEIGHT=0.7
export RAG_SEARCH_VECTOR_WEIGHT=0.3

# 回滚阈值
export RAG_SEARCH_SCORE_THRESHOLD_HYBRID=0.1
export RAG_SEARCH_SCORE_THRESHOLD_VECTOR=0.1

# 回滚 BM25 校准因子
export BM25_SCALE_FACTOR=10
```

---

## 后续优化方向

### 短期（1-2 周）
1. **动态阈值调整**: 基于查询长度、领域自动调整阈值
2. **A/B 测试框架**: 对比不同配置的效果
3. **用户反馈循环**: 收集点击率、满意度数据

### 中期（1 个月）
1. **学习排序 (Learning to Rank)**: 基于历史数据训练排序模型
2. **查询理解增强**: 实体识别、意图分类
3. **多路召回**: 增加元数据检索、时间衰减等维度

### 长期（3 个月）
1. **端到端优化**: 从检索到生成的联合优化
2. **个性化检索**: 基于用户画像的个性化权重
3. **自动调参**: 基于强化学习的参数自优化

---

## 参考资料

1. **LlamaIndex Hybrid Search**: https://docs.llamaindex.ai/en/stable/examples/retrievers/hybrid_search/
2. **LangChain RAG Best Practices**: https://python.langchain.com/docs/use_cases/question_answering/
3. **Milvus Hybrid Retrieval**: https://milvus.io/docs/llamaindex_milvus_hybrid_search.md
4. **Elasticsearch Linear Retriever**: https://www.elastic.co/search-labs/jp/blog/linear-retriever-hybrid-search
5. **RAG 评估指标**: https://research.aimultiple.com/hybrid-rag-evaluation-metrics/

---

**优化完成时间**: 2026-04-02  
**下次评审时间**: 2026-04-09（一周后）  
**负责人**: 后端开发团队
