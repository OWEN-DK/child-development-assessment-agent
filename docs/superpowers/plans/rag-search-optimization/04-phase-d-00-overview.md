# Phase D: 性能优化 (P2)

> **优先级**: P2 (性能优化，可与 B/C 并行)
> **对应需求**: 4.6 (去重优化) + 4.7 (重排序优化) + 4.8 (边界场景处理)
> **对应测试**: 测试 5、6、10

## 🎯 目标

解决 3 个性能与鲁棒性问题：
1. 内容去重使用 O(n²) 算法，100 条结果耗时 100-200ms
2. Cross-Encoder 懒加载导致首次请求延迟 2000-5000ms
3. 边界场景（空查询、超长查询、特殊字符等）未正确处理

## 📋 实施步骤

- [ ] **D-1: content_hash 精确去重**
  - 详见 [04-phase-d-01-hash-dedup.md](./04-phase-d-01-hash-dedup.md)
- [ ] **D-2: MinHash 近似去重**
  - 详见 [04-phase-d-02-minhash-dedup.md](./04-phase-d-02-minhash-dedup.md)
- [ ] **D-3: Cross-Encoder 模型预热**
  - 详见 [04-phase-d-03-reranker-warmup.md](./04-phase-d-03-reranker-warmup.md)
- [ ] **D-4: 动态 initial_k 规则**
  - 详见 [04-phase-d-04-dynamic-initial-k.md](./04-phase-d-04-dynamic-initial-k.md)
- [ ] **D-5: 输入校验与预处理**
  - 详见 [04-phase-d-05-input-validation.md](./04-phase-d-05-input-validation.md)
- [ ] **D-6: 边界年龄映射与降级策略**
  - 详见 [04-phase-d-06-boundary-age-fallback.md](./04-phase-d-06-boundary-age-fallback.md)

## ✅ 验收标准

| 指标 | 当前值 | 目标值 | 负责任务 |
|------|--------|--------|----------|
| 去重算法复杂度 | O(n²) | O(n log n) | D-1, D-2 |
| 去重耗时 (100 条) | ~200ms | ≤50ms | D-1, D-2 |
| 重排序首次延迟 (冷启动) | 2000-5000ms | ≤1500ms | D-3 |
| 重排序后续延迟 | 200-300ms | ≤300ms | D-3 |
| dynamic initial_k | 固定 30 | 15/30/50 | D-4 |
| 边界场景处理 | 未处理 | 合理处理 | D-5, D-6 |

## 🔧 回滚策略

配置项 `rag_performance_optimizations=false` 可禁用所有性能优化。

---

**返回索引：** [00-overview.md](../00-overview.md)
