# 04 - 提示词对比视图 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 04 - 提示词对比视图

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
> **需求点**: 4
> **需求来源**: spec `04-frontend-pages.md` §4.2

## 目标

实现提示词内容 diff 展示，包含变更摘要和影响分析。

## 方案设计

### 组件结构

```
src/features/rag-eval/components/PromptComparison/
├── index.tsx                    # 入口组件
├── PromptDiffView.tsx           # 提示词 diff 展示（双栏）
├── ChangeSummary.tsx            # 变更摘要
├── ImpactAnalysis.tsx           # 影响分析
└── types.ts                     # 类型定义
```

### 对比视图布局

```
┌─────────────────────────────────────────────────────┐
│  提示词对比: 查询重写 Prompt                        │
│  当前版本: v3 (2026-03-20)   建议版本: v4           │
├─────────────────────────────────────────────────────┤
│                                                     │
│  ┌─────────────────────┬─────────────────────┐      │
│  │ 当前版本 (v3)       │ 建议版本 (v4)       │      │
│  │                     │                     │      │
│  │ 你是一个查询...     │ 你是一个查询...     │      │
│  │ 请提取关键词...     │ 请提取关键词...     │      │
│  │ 扩展同义词时...     │ 扩展同义词时...     │      │
│  │                     │ ⚠️ 新增:            │      │
│  │                     │ 同义词必须与...     │      │
│  │                     │ 禁止扩展单字...     │      │
│  │                     │                     │      │
│  └─────────────────────┴─────────────────────┘      │
│                                                     │
│  变更摘要: +2 行约束条件                            │
│  影响分析: 预计降低误杀率 15%，可能降低召回率 3%    │
│                                                     │
│  [采纳建议版本]  [取消]                             │
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

### 影响分析格式

```typescript
interface PromptImpactAnalysis {
  expected_effects: string[]    // ["预计降低误杀率 15%"]
  risk_warnings: string[]       // ["可能降低召回率 3%"]
  affected_features: string[]   // ["查询重写", "同义词扩展"]
}
```

### API 端点

```
GET /api/prompts/{prompt_key}/comparison?current_version={version}&target_version={target_version}
Response:
{
  "prompt_key": "rag_query_rewrite",
  "name_zh": "查询重写提示词",
  "current_version": {
    "version_label": "v3",
    "content": "...",
    "created_at": "2026-03-20"
  },
  "target_version": {
    "version_label": "v4",
    "content": "...",
    "created_at": "2026-04-16"
  },
  "diff": {
    "lines_added": 2,
    "lines_removed": 0,
    "lines_modified": 0,
    "diff_text": "unified diff format..."
  },
  "change_summary": {
    "summary_text": "+2 行约束条件",
    "variables_changed": { ... }
  },
  "impact_analysis": {
    "expected_effects": ["预计降低误杀率 15%"],
    "risk_warnings": ["可能降低召回率 3%"],
    "affected_features": ["查询重写", "同义词扩展"]
  }
}
```

### 验收标准

- [ ] 双栏 diff 展示正确（新增/删除/修改行颜色区分）
- [ ] 变更摘要准确展示行数变化
- [ ] 影响分析展示预期效果和风险警告
- [ ] 支持采纳建议版本或取消
- [ ] 模态框可关闭，状态不丢失
