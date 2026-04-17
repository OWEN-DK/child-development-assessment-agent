# 04 - 提示词编辑页 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 04 - 提示词编辑页

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
> **需求点**: 4
> **需求来源**: spec `07b-prompt-frontend-pages.md`

## 目标

实现提示词编辑页，包含内容编辑 + 变量可视化 + 影响分析面板。

## 方案设计

### 页面布局

```
┌─────────────────────────────────────────────────────┐
│  ← 返回  编辑: 查询重写提示词              [保存]    │
├─────────────────────────────────────────────────────┤
│  当前版本: v4 (2026-04-16)                           │
├───────────────────────────┬─────────────────────────┤
│  内容编辑区                │  变量可视化面板          │
│  ┌───────────────────────┐│  ┌─────────────────────┐│
│  │ 你是一个查询...        ││  │ 变量列表:            ││
│  │ 请提取关键词...        ││  │ • query (string) ✅ ││
│  │ 扩展同义词时...        ││  │ • age (number) ✅   ││
│  │                       ││  │                     ││
│  │ [语法高亮]            ││  │ 影响分析:            ││
│  └───────────────────────┘│  │ • 代码引用: 2 处    ││
│                           │  │ • 配置依赖: 1 项    ││
│                           │  └─────────────────────┘│
└───────────────────────────┴─────────────────────────┘
```

### 核心功能

1. **内容编辑区**: 支持语法高亮，自动提取变量
2. **变量可视化面板**: 展示变量列表，标记是否在内容中使用
3. **影响分析面板**: 展示代码引用位置和配置参数依赖

### 变量自动提取

```typescript
const extractVariables = (content: string): string[] => {
  const pattern = /\{(\w+)\}/g
  const matches = content.matchAll(pattern)
  return Array.from(matches, m => m[1])
}
```

### 保存流程

1. 用户点击 [保存]
2. 前端校验变量是否完整
3. 调用 API 保存新版本
4. 后端自动提取 variables_extracted
5. 计算 change_impact
6. 返回新版本号

### 验收标准

- [ ] 内容编辑区支持语法高亮
- [ ] 变量可视化面板正确展示
- [ ] 影响分析面板展示代码引用和配置依赖
- [ ] 保存时触发变量校验
- [ ] 保存成功后显示新版本号
