# D-4: 动态 initial_k 规则

> **所属 Phase**: Phase D (P2)
> **任务类型**: 单一任务 — 根据查询复杂度动态调整 Cross-Encoder 候选数量
> **对应问题**: 测试 6 问题（固定 initial_k=30，简单查询不需要，复杂查询不够）

## 🎯 目标

根据查询特征动态调整 Cross-Encoder 重排序的 `initial_k` 值，避免简单查询处理过多候选、复杂查询候选不足。

## 📋 实施步骤

- [ ] **Step 1: 分析现有 initial_k 使用**
  - [ ] 阅读 `src/core/reranker.py` 确认 initial_k 使用位置
  - [ ] 确认当前固定值 30 的来源

- [ ] **Step 2: 设计动态规则**
  - [ ] 定义查询复杂度分类：
    - 简单查询（<5 字，无专业术语）→ initial_k=15
    - 中等查询（5-10 字）→ initial_k=30
    - 复杂查询（>10 字，含多个概念）→ initial_k=50
  - [ ] 规则可配置化，通过配置项调整阈值

- [ ] **Step 3: 实现动态 initial_k**
  - [ ] 在 `reranker.py` 中新增 `_calculate_initial_k(query)` 方法
  - [ ] 根据查询长度和关键词数量计算复杂度
  - [ ] 集成到重排序流程，替代固定值 30
  - [ ] 添加配置项 `rag_reranker_dynamic_initial_k` 开关

- [ ] **Step 4: 编写单元测试**
  - [ ] 测试 4 种查询类型的 initial_k 计算（需求文档测试 6 的 4 条数据）
  - [ ] 验证简单查询 initial_k ≤20
  - [ ] 验证复杂查询 initial_k ≥50

- [ ] **Step 5: 性能验证**
  - [ ] 确认动态 initial_k 不影响重排序质量
  - [ ] 确认简单查询响应时间降低

## ✅ 验收标准

| 查询类型 | 示例 | 当前 initial_k | 目标 initial_k |
|----------|------|----------------|----------------|
| 简单 | 运动 | 30 | 15 |
| 中等 | 感统训练方法 | 30 | 30 |
| 短词 | 前庭觉 | 30 | 20 |
| 复杂 | 3 岁孩子注意力不集中怎么办 | 30 | 50 |

- 动态 initial_k 根据查询复杂度正确计算
- 配置项可开关动态规则

## 📁 涉及文件

| 文件 | 操作 | 说明 |
|------|------|------|
| `src/core/reranker.py` | 修改 | 新增动态 initial_k 计算 |
| `src/config/settings.py` | 修改 | 新增 initial_k 配置项 |
| `tests/test_dynamic_initial_k.py` | 新增 | 单元测试 |

---

**返回索引：** [04-phase-d-00-overview.md](./04-phase-d-00-overview.md)
