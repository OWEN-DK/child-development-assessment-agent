# 03 - 分类配置页 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 03 - 分类配置页

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

> **Phase**: 8
> **需求点**: 3
> **需求来源**: spec `08b-config-frontend-pages.md`

## 目标

实现单个功能域的配置项列表与编辑功能。

## 方案设计

### 页面布局

```
┌─────────────────────────────────────────────────────┐
│  ← 返回  RAG 检索配置                                │
├─────────────────────────────────────────────────────┤
│  ┌───────────────────────────────────────────────┐  │
│  │ BM25 TopK                                     │  │
│  │ 说明: BM25 检索返回的文档数量                   │  │
│  │ 当前值: [10]  推荐范围: [5, 50]                │  │
│  │ 影响组件: BM25 检索器                           │  │
│  │ 重载方式: 热重载                                │  │
│  │ [保存]                                         │  │
│  └───────────────────────────────────────────────┘  │
│                                                     │
│  ┌───────────────────────────────────────────────┐  │
│  │ 向量检索 TopK                                  │  │
│  │ 说明: 向量检索返回的文档数量                    │  │
│  │ 当前值: [10]  推荐范围: [5, 50]                │  │
│  │ 影响组件: 向量检索器                            │  │
│  │ 重载方式: 热重载                                │  │
│  │ [保存]                                         │  │
│  └───────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────┘
```

### 编辑表单组件

```typescript
interface ConfigItemForm {
  key: string
  name_zh: string
  description_zh: string
  current_value: any
  value_type: 'string' | 'number' | 'boolean' | 'json'
  min_value?: number
  max_value?: number
  recommended_min?: number
  recommended_max?: number
  unit?: string
  affected_components: string[]
  reload_type: 'hot' | 'cold'
}
```

### 验收标准

- [ ] 展示单个功能域的所有配置项
- [ ] 每个配置项有中文说明
- [ ] 支持编辑配置值
- [ ] 展示影响组件和重载方式
- [ ] 保存后触发热重载（如适用）
