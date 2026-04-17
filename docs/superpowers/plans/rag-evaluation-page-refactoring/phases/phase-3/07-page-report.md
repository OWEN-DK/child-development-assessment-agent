# 07 - 评估报告页 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 07 - 评估报告页

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

## 路由

`/rag-eval/reports/{id}`

## 实施文件

`frontend/src/features/rag-eval/pages/ReportPage.tsx`

## 页面功能

1. 指标总览（雷达图/柱状图）
2. 6 层校验结果展示
3. 推荐模式面板（参数调优/提示词优化）
4. 趋势图（多版本对比）
5. 导出功能（PDF/CSV/JSON）

## 页面布局

```
┌─────────────────────────────────────────────────────┐
│  ← 返回          评估报告                             │
│  测试集：xxx | 运行：xxx | 配置版本：v1.2.0 | 生成时间  │
│                                              [导出 ▼] │
├─────────────────────────────────────────────────────┤
│  [Tab] 指标总览  [Tab] 6层校验  [Tab] 调优建议        │
│       [Tab] 趋势追踪  [Tab] Bad Case                 │
├─────────────────────────────────────────────────────┤
│                                                     │
│  指标总览 Tab:                                       │
│  ┌────────────┐ ┌─────────────────────────────────┐ │
│  │ 雷达图      │ │ 核心指标卡片                     │ │
│  │ P@1 R@1    │ │ P@1: 0.84  R@5: 0.86            │ │
│  │ P@3 R@3    │ │ MRR: 0.71  NDCG@5: 0.79         │ │
│  │ P@5 R@5    │ │ HR@5: 0.96  延迟: 245ms          │ │
│  │ MRR NDCG   │ │                                 │ │
│  └────────────┘ └─────────────────────────────────┘ │
│                                                     │
│  6层校验 Tab:                                        │
│  ┌───────────────────────────────────────────────┐  │
│  │ Layer 1: 基础检索质量    ✓ PASS  0.84/0.70    │  │
│  │ Layer 2: 领域覆盖度      ⚠ WARN  0.65/0.70    │  │
│  │ Layer 3: 语义一致性      ✓ PASS  0.92/0.80    │  │
│  │ Layer 4: 边界条件        ✓ PASS  0.78/0.70    │  │
│  │ Layer 5: 意图识别        ✓ PASS  0.88/0.80    │  │
│  │ Layer 6: 综合评估        ⚠ WARN               │  │
│  └───────────────────────────────────────────────┘  │
│                                                     │
│  调优建议 Tab:                                       │
│  ┌───────────────────────────────────────────────┐  │
│  │ 参数建议:                                      │  │
│  │ • chunk_size: 512 → 768 (预计提升 P@1 +3%)    │  │
│  │ • top_k: 5 → 8 (预计提升 R@5 +5%)             │  │
│  │                              [采纳] [忽略]     │  │
│  │                                               │  │
│  │ 提示词建议:                                    │  │
│  │ • 检索提示词版本 v1.2 → v1.3                  │  │
│  │                              [预览] [采纳]     │  │
│  └───────────────────────────────────────────────┘  │
│                                                     │
│  趋势追踪 Tab:                                       │
│  ┌───────────────────────────────────────────────┐  │
│  │ 折线图：P@1 / R@5 / MRR 随配置版本变化趋势      │  │
│  │ 误差线 + 多指标叠加 + hover 详情               │  │
│  └───────────────────────────────────────────────┘  │
│                                                     │
│  Bad Case Tab:                                      │
│  ┌───────────────────────────────────────────────┐  │
│  │ 查询语句 | 预期文档 | 实际命中 | 差距分析        │  │
│  │ ...                                          │  │
│  └───────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────┘
```

## API 接口

### 获取报告详情

```
GET /api/reports/{id}
```

响应：
```json
{
  "id": "uuid",
  "run_id": "uuid",
  "test_set_id": "uuid",
  "test_set_name": "3-5岁运动发展测试集",
  "run_name": "第3次运行",
  "config_version_id": "uuid",
  "config_version_label": "v1.2.0",
  "metrics": {
    "precision_at_1": 0.84,
    "precision_at_3": 0.78,
    "precision_at_5": 0.72,
    "recall_at_1": 0.62,
    "recall_at_3": 0.78,
    "recall_at_5": 0.86,
    "mrr": 0.71,
    "ndcg_at_5": 0.79,
    "hit_rate_at_5": 0.96,
    "avg_latency_ms": 245
  },
  "validation_results": [...],
  "tuning_suggestions": [...],
  "prompt_suggestions": [...],
  "bad_cases": [...],
  "created_at": "2026-04-17T10:03:07Z"
}
```

### 导出报告

```
POST /api/reports/{id}/export
{
  "format": "pdf"  // pdf | csv | json
}
```

### 获取趋势数据

```
GET /api/reports/trend?test_set_id=uuid&metrics=p@1,r@5,mrr
```

## 6 层校验展示

每层校验结果包含：

| 字段 | 说明 |
|------|------|
| layer | 层序号（1-6） |
| name | 层名称 |
| status | pass/warn/fail |
| score | 实际得分 |
| threshold | 阈值 |
| duration_ms | 校验耗时 |
| details | 详细说明（JSON） |

## 交互细节

- 雷达图使用 ECharts 或 Ant Design Charts
- 趋势图支持选择指标组合、时间范围、配置版本分组
- Bad Case 列表支持点击展开详情（预期文档 vs 实际命中对比）
- 导出为异步任务，完成后通过导出 SSE 通道通知
- 推荐面板的"采纳"操作进入审查→保存三步流程（Phase-5 实现）
