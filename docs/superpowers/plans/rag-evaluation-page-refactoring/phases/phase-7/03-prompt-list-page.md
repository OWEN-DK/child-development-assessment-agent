# 03 - 提示词列表页 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 03 - 提示词列表页

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
> **需求点**: 3
> **需求来源**: spec `07b-prompt-frontend-pages.md`

## 目标

实现提示词列表页，展示中文名称 + 用途说明 + 当前版本号 + 使用状态。

## 方案设计

### 页面布局

```
┌─────────────────────────────────────────────────────┐
│  提示词管理                                          │
├─────────────────────────────────────────────────────┤
│  [搜索框] [筛选: 分类 ▼]                             │
├─────────────────────────────────────────────────────┤
│  ┌───────────────────────────────────────────────┐  │
│  │ 中文名称      │ 分类   │ 当前版本 │ 状态   │ 操作│  │
│  ├───────────────────────────────────────────────┤  │
│  │ 查询重写提示词 │ 检索   │ v4      │ 使用中 │ 编辑│  │
│  │ 同义词扩展提示词│ 检索   │ v2      │ 使用中 │ 编辑│  │
│  │ 报告生成提示词 │ 报告   │ v1      │ 未引用 │ 编辑│  │
│  └───────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────┘
```

### 展示字段

| 列 | 数据来源 | 说明 |
|----|---------|------|
| 中文名称 | PromptMetadata.name_zh | 点击跳转到编辑页 |
| 分类 | PromptMetadata.category | 展示中文映射 |
| 当前版本 | PromptVersion.version_label | 最新版本的版本号 |
| 使用状态 | 代码引用扫描结果 | 使用中/未引用 |
| 操作 | - | [编辑] [版本历史] |

### API 端点

```
GET /api/prompts?page=1&page_size=20&category=rag_retrieval
Response:
{
  "items": [
    {
      "prompt_key": "rag_query_rewrite",
      "name_zh": "查询重写提示词",
      "purpose": "将用户原始查询重写为更适合知识库检索的形式",
      "category": "rag_retrieval",
      "current_version": {
        "version_label": "v4",
        "created_at": "2026-04-16T10:00:00Z"
      },
      "is_referenced": true,
      "reference_count": 2
    }
  ],
  "total": 10
}
```

### 验收标准

- [ ] 列表展示中文名称和用途
- [ ] 显示当前版本号和最后修改时间
- [ ] 显示使用状态（是否被代码引用）
- [ ] 支持按分类筛选
- [ ] 支持搜索提示词名称
