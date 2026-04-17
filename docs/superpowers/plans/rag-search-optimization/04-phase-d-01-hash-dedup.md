# D-1: content_hash 精确去重

> **所属 Phase**: Phase D (P2)
> **任务类型**: 单一任务 — 利用文档导入时已计算的 content_hash 进行 O(n) 精确去重
> **对应问题**: 测试 5 部分问题（未利用 content_hash 快速过滤）

## 🎯 目标

利用文档导入阶段已计算的 `content_hash` (MD5) 进行快速精确去重，替代部分 O(n²) 的 SequenceMatcher 比较。

## 📋 实施步骤

- [ ] **Step 1: 分析现有 content_hash 使用情况**
  - [ ] 阅读 `src/service/document_ingestion_service.py` 确认 content_hash 计算与存储位置
  - [ ] 阅读 `src/core/hybrid_retrieval.py` 或 `src/core/result_fusion.py` 确认检索结果是否携带 content_hash
  - [ ] 确认 content_hash 在检索结果中的可用性

- [ ] **Step 2: 实现 hash 精确去重**
  - [ ] 在去重流程第一步使用 dict/set 按 content_hash 快速过滤完全相同内容
  - [ ] 保留 hash 冲突时 relevance_score 更高的条目
  - [ ] 复杂度 O(n)，100 条结果耗时 <5ms

- [ ] **Step 3: 编写单元测试**
  - [ ] 测试完全相同内容（hash 相同）的去重
  - [ ] 测试 hash 不同但内容相似的情况（留给 MinHash 处理）
  - [ ] 测试空结果、单条结果等边界情况

- [ ] **Step 4: 性能验证**
  - [ ] 基准测试：100 条结果 hash 去重耗时 <5ms
  - [ ] 确认去重准确率 100%（hash 相同必为相同内容）

## ✅ 验收标准

- content_hash 精确去重复杂度 O(n)
- 100 条结果耗时 <5ms
- 去重准确率 100%

## 📁 涉及文件

| 文件 | 操作 | 说明 |
|------|------|------|
| `src/core/rag/dedup_engine.py` | 新增 | hash 精确去重实现 |
| `tests/test_hash_dedup.py` | 新增 | 单元测试 |

---

**返回索引：** [04-phase-d-00-overview.md](./04-phase-d-00-overview.md)
