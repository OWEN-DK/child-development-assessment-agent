# 05 - 提示词版本对比页 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 05 - 提示词版本对比页

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

> **Phase**: 7
> **需求点**: 5
> **需求来源**: spec `07b-prompt-frontend-pages.md`

## 目标

实现提示词版本对比页，diff 可视化 + 变更摘要。

## 方案设计

### 页面布局

```
┌─────────────────────────────────────────────────────┐
│  ← 返回  版本对比: 查询重写提示词                    │
│  v3 (2026-03-20) vs v4 (2026-04-16)                  │
├─────────────────────────────────────────────────────┤
│                                                     │
│  ┌─────────────────────┬─────────────────────┐      │
│  │ 当前版本 (v3)       │ 目标版本 (v4)       │      │
│  │                     │                     │      │
│  │ 你是一个查询...     │ 你是一个查询...     │      │
│  │ 请提取关键词...     │ 请提取关键词...     │      │
│  │ 扩展同义词时...     │ 扩展同义词时...     │      │
│  │                     │ + 同义词必须与...   │      │
│  │                     │ + 禁止扩展单字...   │      │
│  └─────────────────────┴─────────────────────┘      │
│                                                     │
│  变更摘要: +2 行约束条件                            │
│  变量变更: 无变化                                    │
│                                                     │
│  [回滚到此版本]  [返回列表]                          │
└─────────────────────────────────────────────────────┘
```

### Diff 展示规则

1. **新增行**: 绿色背景 + `+` 前缀
2. **删除行**: 红色背景 + `-` 前缀
3. **修改行**: 黄色背景，展示修改前后差异
4. **未变更行**: 正常展示，作为上下文

### 变更摘要格式

```typescript
interface PromptChangeSummary {
  lines_added: number
  lines_removed: number
  lines_modified: number
  variables_changed: {
    added: string[]
    removed: string[]
    modified: string[]
  }
  summary_text: string  // "+2 行约束条件"
}
```

### 验收标准

- [ ] 双栏 diff 展示正确
- [ ] 变更摘要准确
- [ ] 变量变更检测正确
- [ ] 支持回滚到此版本
