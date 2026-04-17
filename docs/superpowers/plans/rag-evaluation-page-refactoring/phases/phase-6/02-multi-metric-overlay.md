# 02 - 多指标叠加展示 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 02 - 多指标叠加展示

**Architecture:** 参考下方原文档的实现方案和数据模型

**Tech Stack:** Python, FastAPI, TypeScript, React

---

### Task 1: 实现核心逻辑与测试

**Files:**
- Test: `tests/test_placeholder.py`

- [ ] **Step 1: Write the failing test**
  - 根据下方的验收标准和测试方案，编写对应的测试用例
- [ ] **Step 2: Run test to verify it fails**
  - 执行测试并确保看到预期失败信息 (Red)
- [ ] **Step 3: Write minimal implementation**
  - 根据下方"实现方案"中的步骤，编写或修改业务代码
- [ ] **Step 4: Run test to verify it passes**
  - 执行测试确保通过 (Green)
- [ ] **Step 5: Commit**
  - `git add` 相关文件并提交 commit

---

## 原始需求与设计细节 (供参考)

> **Phase**: 6
> **需求点**: 2
> **需求来源**: spec `04-frontend-pages.md` §4.9

## 目标

实现多指标在同一图表中叠加展示，每个指标使用独立 Y 轴。

## 方案设计

### 组件结构

```
src/features/rag-eval/components/TrendChart/MultiMetricChart/
├── index.tsx                    # 入口组件
├── MetricLegend.tsx             # 指标图例
├── DualYAxis.tsx                # 双 Y 轴组件
└── types.ts                     # 类型定义
```

### 交互设计

```
┌─────────────────────────────────────────────────────────┐
│  指标趋势 (按配置版本)                                   │
├─────────────────────────────────────────────────────────┤
│  P@5  ┃         ╱╲                                      │
│  R@5  ┃──────╱─────╲────                               │
│        ┗━━━━━━━━━━━━━━━━━━━━━━━━━━━                     │
│        v1.0     v2.0     v2.1     v2.2     v2.3        │
│                                                         │
│  [指标切换: ☑ P@5 | ☑ R@5 | ☐ F1 | ☐ MRR | ☐ NDCG]    │
└─────────────────────────────────────────────────────────┘
```

### 图例交互

1. 图例可点击切换显示/隐藏
2. 点击图例项，切换该指标的显示状态
3. 至少保留一个指标显示（不允许全部隐藏）

### 双 Y 轴策略

| 指标数量 | Y 轴策略 |
|---------|---------|
| 1 个指标 | 单 Y 轴，居中展示 |
| 2 个指标 | 双 Y 轴，左侧显示第一个指标，右侧显示第二个指标 |
| 3+ 个指标 | 双 Y 轴，前两个指标使用 Y 轴，其他指标复用其中一个 Y 轴（按量级分组） |

### 指标颜色与 Y 轴映射

```typescript
const METRIC_CONFIG = {
  p_at_5: { color: '#1890ff', label: 'P@5', yAxis: 'left' },
  r_at_5: { color: '#52c41a', label: 'R@5', yAxis: 'right' },
  f1: { color: '#fa8c16', label: 'F1', yAxis: 'left' },
  mrr: { color: '#722ed1', label: 'MRR', yAxis: 'right' },
  ndcg: { color: '#f5222d', label: 'NDCG', yAxis: 'left' }
}
```

### 数据格式

```typescript
interface MultiMetricTrendData {
  versions: {
    version_id: string
    version_label: string
    created_at: string
  }[]
  metrics: {
    [metric: string]: {
      [version_id: string]: {
        mean: number
        min: number
        max: number
        run_count: number
      }
    }
  }
}
```

### API 端点

```
GET /api/trends/{test_set_id}?metrics=p_at_5,r_at_5,f1&days=7
Response:
{
  "versions": [...],
  "metrics": {
    "p_at_5": {
      "version_id_1": { "mean": 0.57, "min": 0.53, "max": 0.61, "run_count": 3 },
      ...
    },
    "r_at_5": { ... },
    "f1": { ... }
  }
}
```

### 验收标准

- [ ] 支持多指标叠加展示
- [ ] 每个指标使用独立 Y 轴
- [ ] 图例可点击切换显示/隐藏
- [ ] 不同指标颜色区分
- [ ] 至少保留一个指标显示
