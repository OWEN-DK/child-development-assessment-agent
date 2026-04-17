# 诊断测试验收报告

## 测试集概览

| 指标 | 值 |
|------|------|
| 测试项总数 | 12 |
| 当前通过 | 2 |
| 当前失败 | 10 |
| 当前通过率 | 17% |
| 目标通过率 | 100% |

## 测试与 Phase 映射

| 测试项 | 当前状态 | 负责 Phase | 验收标准 |
|--------|----------|------------|----------|
| 测试 1: 检索质量指标 | ❌ P@5=0.53 | Phase A | P@5≥0.75, R@5≥0.70, NDCG@5≥0.80, MRR≥0.75, HR@5≥0.85 |
| 测试 2: 分数分布分析 | ❌ 差异=0.80 | Phase A | BM25 与向量分数差异 <0.2 |
| 测试 3: 年龄适配度细粒度 | ❌ 3 档 | Phase A | ≥10 个不同值 (0-1 连续分布) |
| 测试 4: 查询类型分析 | ❌ 固定权重 | Phase B | 短查询向量权重 ≥0.6, 专业术语 BM25 权重 ≥0.6 |
| 测试 5: 内容去重效果 | ❌ O(n²) | Phase D | 正确去重，复杂度 O(n log n)，耗时 ≤50ms |
| 测试 6: 重排序效果 | ❌ 固定 initial_k | Phase D | 动态 initial_k，首次延迟 ≤1500ms |
| 测试 7: 性能分析 | ❌ P50=800ms | Phase D | P50≤300ms, P95≤500ms, P99≤800ms (预热后) |
| 测试 8: 稳定性分析 | ✅ | - | 分数波动标准差 <0.05 (保持) |
| 测试 9: 相关性一致性 | ✅ | - | 相同内容对不同查询分数合理 (保持) |
| 测试 10: 边界场景分析 | ❌ 未处理 | Phase D | 所有边界场景有合理处理 |
| 测试 11: 年龄过滤准确性 | ❌ 71% | Phase A | 过滤准确率 ≥90% |
| 测试 12: 同义词扩展质量 | ❌ 高噪声 | Phase C | 质量验证通过率 ≥95%, 兜底成功率 ≥80% |

## 验证方法

### Phase A 验证

```bash
# 运行诊断测试
cd backend
uv run python tests/diagnose_rag_comprehensive_v2.py

# 关注指标:
# - 测试 1: Precision@5 ≥ 0.75
# - 测试 2: BM25 与向量分数差异 < 0.2
# - 测试 3: 年龄适配度不同值数量 ≥ 10
# - 测试 11: 年龄过滤准确率 ≥ 90%
```

### Phase B 验证

```bash
# 运行查询类型分析测试
cd backend
uv run python tests/diagnose_rag_comprehensive_v2.py --test query_type_analysis

# 关注指标:
# - 短查询 (<5 字): 向量权重 ≥ 0.6
# - 专业术语查询: BM25 权重 ≥ 0.6
```

### Phase C 验证

```bash
# 运行同义词扩展质量测试
cd backend
uv run python tests/diagnose_rag_comprehensive_v2.py --test synonym_quality

# 关注指标:
# - 同义词质量验证通过率 ≥ 95%
# - LLM 失败时本地兜底成功率 ≥ 80%
```

### Phase D 验证

```bash
# 运行性能测试
cd backend
uv run python tests/diagnose_rag_comprehensive_v2.py --test performance

# 关注指标:
# - 去重耗时 ≤ 50ms (100 条结果)
# - 重排序首次延迟 ≤ 1500ms
# - P50 响应时间 ≤ 300ms (预热后)
# - P95 响应时间 ≤ 500ms (预热后)
# - P99 响应时间 ≤ 800ms (预热后)
```

---

**最后更新：** 2026-04-15
