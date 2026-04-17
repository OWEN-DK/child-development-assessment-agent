# 03 - 配置对比视图 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 03 - 配置对比视图

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

> **Phase**: 5
> **需求点**: 3
> **需求来源**: spec `04-frontend-pages.md` §4.2

## 目标

实现配置修改前后 diff 展示，包含历史参考。

## 方案设计

### 组件结构

```
src/features/rag-eval/components/ConfigComparison/
├── index.tsx                    # 入口组件
├── ConfigDiffView.tsx           # 配置 diff 展示
├── HistoryReference.tsx         # 历史参考展示
└── types.ts                     # 类型定义
```

### 对比视图布局

```
┌─────────────────────────────────────────────────────┐
│  配置对比: BM25 TopK                                │
├─────────────────────────────────────────────────────┤
│                                                     │
│  当前值 (v2.3)          建议值          自定义值     │
│  ┌──────────────┐       ┌──────────────┐  ┌──────┐ │
│  │   10         │  →    │   15         │  │ [12] │ │
│  └──────────────┘       └──────────────┘  └──────┘ │
│                                                     │
│  历史参考:                                          │
│  • v2.1 (2026-03-15): 10→12, P@5+0.05, R@5 不变    │
│  • v1.8 (2026-02-20): 8→10, P@5+0.08, R@5+0.02     │
│                                                     │
│  安全范围: [5, 50]  推荐范围: [10, 20]              │
│                                                     │
│  [采纳建议值 (15)]  [采纳自定义值 (12)]  [取消]     │
└─────────────────────────────────────────────────────┘
```

### 数据流

1. 用户点击推荐项的 [查看对比] 按钮
2. 弹出模态框，展示配置对比视图
3. 从 API 获取：当前值、建议值、历史变更记录、安全范围、推荐范围
4. 用户可选择采纳建议值或输入自定义值
5. 确认后关闭模态框，返回主面板

### API 端点

```
GET /api/config/{param_name}/comparison?current_version={version}
Response:
{
  "param_name": "bm25_top_k",
  "name_zh": "BM25 TopK",
  "current_value": 10,
  "current_version": "v2.3",
  "suggested_value": 15,
  "safe_range": [5, 50],
  "recommended_range": [10, 20],
  "history": [
    {
      "version": "v2.1",
      "changed_at": "2026-03-15",
      "old_value": 10,
      "new_value": 12,
      "effect": "P@5+0.05, R@5 不变"
    }
  ]
}
```

### 验收标准

- [ ] 对比视图展示当前值、建议值、自定义值输入框
- [ ] 历史参考展示至少 2 条变更记录
- [ ] 安全范围和推荐范围正确展示
- [ ] 支持采纳建议值或自定义值
- [ ] 模态框可关闭，状态不丢失
