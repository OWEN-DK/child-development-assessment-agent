# 09 - 删除 OneClickOptimize 组件 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 09 - 删除 OneClickOptimize 组件

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

## 目标

删除 `OneClickOptimize` 组件，该组件违反"禁止替用户决策"原则。

## 问题根因

`OneClickOptimize` 组件允许用户一键应用系统推荐的配置优化，但这剥夺了用户对配置变更的审查权。在 RAG 调优场景中，配置变更可能影响检索质量，用户必须经过"预览→审查→确认"流程后才能应用。

## 删除清单

| 文件 | 说明 |
|------|------|
| `frontend/src/features/rag-evaluation/components/OneClickOptimize.tsx` | 组件主体 |

## 引用清理

删除前需检查以下位置的引用并清理：

1. `frontend/src/features/rag-evaluation/pages/RagEvaluationPage.tsx` — 旧页面中的 import 和使用（随旧页面一起删除）
2. `frontend/src/features/rag-evaluation/index.ts` — 导出语句（随旧导出文件一起删除）
3. 其他可能的引用 — 使用 `grep -r "OneClickOptimize" frontend/src/` 全局搜索确认

## 替代方案

Phase-5 将实现"推荐模式面板"，采用三步分离流程：

```
推荐展示 → 用户采纳 → 审查变更 → 保存为新版本
```

与 OneClickOptimize 的区别：
- 不直接应用变更，必须经过审查
- 保存为新配置版本，不覆盖当前版本
- 支持对比 diff，清晰展示变更内容
- 支持回滚到历史版本

## 验证步骤

1. 删除后运行 `npm run build` 确认无编译错误
2. 全局搜索确认无残留引用
3. 确认旧页面删除后，此组件无其他引用点
