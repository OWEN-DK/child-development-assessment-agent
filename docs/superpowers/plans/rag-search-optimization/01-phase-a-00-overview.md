# Phase A: 分数语义重构 (P0)

> **优先级**: P0 (核心问题，必须首先完成)
> **对应需求**: 4.1 (分数语义重构) + 4.2 (年龄适配度细粒度化) + 4.3 (分数校准统一)
> **对应测试**: 测试 1、2、3、11

## 🎯 目标

解决 3 个根因问题：
1. `relevance_score` 混合了检索相关性和年龄适配度，分数语义不清
2. 年龄适配度仅三档固定值 (0.3, 0.7, 1.0)，无法细粒度区分
3. BM25 和向量分数不在同一量级，融合后排序失真

## 📋 实施步骤

- [ ] **A-1: 分数分离与数据模型变更**
  - 详见 [01-phase-a-01-score-separation.md](./01-phase-a-01-score-separation.md)
- [ ] **A-2: 年龄适配度细粒度计算器**
  - 详见 [01-phase-a-02-age-fit-scorer.md](./01-phase-a-02-age-fit-scorer.md)
- [ ] **A-3: BM25/向量分数校准统一**
  - 详见 [01-phase-a-03-score-calibration.md](./01-phase-a-03-score-calibration.md)
- [ ] **A-4: 年龄过滤逻辑重构**
  - 详见 [01-phase-a-04-age-filter-refactor.md](./01-phase-a-04-age-filter-refactor.md)
- [ ] **A-5: 过滤流水线集成**
  - 详见 [01-phase-a-05-filter-pipeline-integration.md](./01-phase-a-05-filter-pipeline-integration.md)
- [ ] **A-6: 前端分数展示适配**
  - 详见 [01-phase-a-06-frontend-adaptation.md](./01-phase-a-06-frontend-adaptation.md)

## ✅ 验收标准

| 指标 | 当前值 | 目标值 |
|------|--------|--------|
| Precision@5 | 0.53 | ≥0.75 |
| 年龄适配度不同值数量 | 3 | ≥10 |
| 年龄过滤准确率 | 71% | ≥90% |
| BM25 与向量分数最大差异 | 0.80 | <0.2 |

## 🔧 回滚策略

配置项 `rag_score_method=legacy` 可恢复旧版混合分数计算。

---

**返回索引：** [00-overview.md](../00-overview.md)
