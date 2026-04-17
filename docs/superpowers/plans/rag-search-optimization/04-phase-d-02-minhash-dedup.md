# D-2: MinHash 近似去重

> **所属 Phase**: Phase D (P2)
> **任务类型**: 单一任务 — 使用 MinHash + LSH 实现 O(n log n) 语义近似去重
> **对应问题**: 测试 5 主要问题（O(n²) 算法性能差）

## 🎯 目标

在 hash 精确去重之后，使用 MinHash + LSH (Locality Sensitive Hashing) 对语义相似但内容不同的块进行近似去重，将复杂度从 O(n²) 降至 O(n log n)。

## 📋 实施步骤

- [ ] **Step 1: 调研 MinHash + LSH 方案**
  - [ ] 确认 `datasketch` 库的 MinHash 和 MinHashLSH API
  - [ ] 确定合适的 hash 函数数量（通常 128-256）和相似度阈值（建议 0.7-0.8）
  - [ ] 确定中文文本的分词策略（jieba 分词后计算 MinHash）

- [ ] **Step 2: 实现 MinHash 近似去重**
  - [ ] 对每条检索结果内容计算 MinHash 签名
  - [ ] 使用 LSH 分桶，仅桶内比较，避免 O(n²)
  - [ ] 相似度超过阈值的条目，保留 relevance_score 更高的
  - [ ] 集成到去重流程第二步（hash 精确去重之后）

- [ ] **Step 3: 编写单元测试**
  - [ ] 测试语义相似内容的去重效果
  - [ ] 测试不同内容不被误去重
  - [ ] 测试 100 条结果的性能（耗时 ≤50ms）

- [ ] **Step 4: 性能验证**
  - [ ] 基准测试：100 条结果 MinHash 去重耗时 ≤50ms
  - [ ] 确认复杂度 O(n log n)

## ✅ 验收标准

- MinHash 近似去重复杂度 O(n log n)
- 100 条结果耗时 ≤50ms
- 语义相似内容正确去重，不同内容不误去重

## 📁 涉及文件

| 文件 | 操作 | 说明 |
|------|------|------|
| `src/core/rag/dedup_engine.py` | 修改 | 新增 MinHash 近似去重 |
| `src/config/settings.py` | 修改 | 新增 MinHash 配置项（阈值、hash 数量） |
| `tests/test_minhash_dedup.py` | 新增 | 单元测试 |
| `pyproject.toml` | 修改 | 新增 `datasketch` 依赖 |

---

**返回索引：** [04-phase-d-00-overview.md](./04-phase-d-00-overview.md)
