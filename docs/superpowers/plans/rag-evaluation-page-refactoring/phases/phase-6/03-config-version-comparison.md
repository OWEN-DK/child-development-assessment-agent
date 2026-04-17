# 03 - 配置版本对比 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 03 - 配置版本对比

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
> **需求点**: 3
> **需求来源**: spec `04-frontend-pages.md` §4.9

## 目标

实现配置版本对比功能，展示变更项并使用 ✨ 标记。

## 方案设计

### 组件结构

```
src/features/rag-eval/components/ConfigVersionComparison/
├── index.tsx                    # 入口组件
├── ComparisonTable.tsx          # 对比表格
├── ChangeHighlight.tsx          # 变更高亮
└── types.ts                     # 类型定义
```

### 对比视图布局

```
┌─────────────────────────────────────────┐
│  配置版本对比                            │
├─────────────────────────────────────────┤
│  参数           │ v2.2      │ v2.3      │
├─────────────────────────────────────────┤
│  bm25_top_k     │ 10        │ 15 ✨     │
│  vector_top_k   │ 10        │ 10        │
│  fusion_threshold│ 0.25     │ 0.25      │
│  reranker_initial_k │ 30    │ 40 ✨     │
└─────────────────────────────────────────┘

✨ 标记变更项
```

### 展示规则

1. **变更项**: 使用 ✨ 标记，值使用不同颜色（新增/增大用绿色，减少用红色）
2. **未变更项**: 正常展示，无特殊标记
3. **仅存在于一个版本的参数**: 标记为"新增"或"删除"

### API 端点

```
GET /api/config-versions/compare?from_version={version_id}&to_version={version_id}
Response:
{
  "from_version": {
    "version_label": "v2.2",
    "config_snapshot": { ... }
  },
  "to_version": {
    "version_label": "v2.3",
    "config_snapshot": { ... }
  },
  "changes": {
    "bm25_top_k": { "old": 10, "new": 15, "changed": true },
    "vector_top_k": { "old": 10, "new": 10, "changed": false },
    "reranker_initial_k": { "old": 30, "new": 40, "changed": true }
  }
}
```

### 验收标准

- [ ] 对比表格正确展示两个版本的配置值
- [ ] 变更项使用 ✨ 标记
- [ ] 变更值颜色区分（增大/减少）
- [ ] 支持任意两个版本对比
