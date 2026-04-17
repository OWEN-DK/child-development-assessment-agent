# 01 - /rag-eval/* 路由配置 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 01 - /rag-eval/* 路由配置

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

在 React Router 7 中配置 `/rag-eval/*` 下的所有子路由，替代旧的 `/rag-evaluation` 单路由。

## 路由树

```
/rag-eval
  ├── /test-sets                    → TestSetListPage
  │   └── /:id                      → TestSetDetailPage
  │       └── /drafts               → DraftReviewPage
  ├── /runs                         → RunListPage
  │   └── /:id                      → RunDetailPage
  └── /reports/:id                  → ReportPage
```

## 实施文件

`frontend/src/router/index.tsx`

## 修改方案

### 修改前（现有路由）

```typescript
{
  path: '/rag-evaluation',
  element: <RagEvaluationPage />,
}
```

### 修改后

```typescript
import { lazy, Suspense } from 'react';
import { Outlet } from 'react-router-dom';
import { Spin } from 'antd';

// 懒加载各页面
const TestSetListPage = lazy(() => import('@/features/rag-eval/pages/TestSetListPage'));
const TestSetDetailPage = lazy(() => import('@/features/rag-eval/pages/TestSetDetailPage'));
const DraftReviewPage = lazy(() => import('@/features/rag-eval/pages/DraftReviewPage'));
const RunListPage = lazy(() => import('@/features/rag-eval/pages/RunListPage'));
const RunDetailPage = lazy(() => import('@/features/rag-eval/pages/RunDetailPage'));
const ReportPage = lazy(() => import('@/features/rag-eval/pages/ReportPage'));

// 布局组件
const RagEvalLayout = () => (
  <Suspense fallback={<Spin size="large" style={{ display: 'block', marginTop: 100 }} />}>
    <Outlet />
  </Suspense>
);

// 路由配置
{
  path: '/rag-eval',
  element: <RagEvalLayout />,
  children: [
    {
      index: true,
      element: <Navigate to="/rag-eval/test-sets" replace />,
    },
    {
      path: 'test-sets',
      children: [
        { index: true, element: <TestSetListPage /> },
        { path: ':id', element: <TestSetDetailPage /> },
        { path: ':id/drafts', element: <DraftReviewPage /> },
      ],
    },
    {
      path: 'runs',
      children: [
        { index: true, element: <RunListPage /> },
        { path: ':id', element: <RunDetailPage /> },
      ],
    },
    {
      path: 'reports/:id',
      element: <ReportPage />,
    },
  ],
}
```

## 懒加载策略

- 所有页面组件使用 `lazy()` 懒加载，减少首屏包体积
- 使用 `Suspense` 包裹，fallback 为 Ant Design `Spin` 组件
- `RagEvalLayout` 作为共享布局，统一处理加载状态

## 菜单配置

同步更新 `frontend/src/App.tsx` 中的 `menuDataRender()`：

```typescript
{
  key: '/rag-eval',
  label: 'RAG 评估',
  icon: <ExperimentOutlined />,
  children: [
    { key: '/rag-eval/test-sets', label: '测试集管理' },
    { key: '/rag-eval/runs', label: '运行历史' },
  ],
}
```

## 注意事项

- 旧路由 `/rag-evaluation` 在 Phase-3 的 `08-delete-old-routes.md` 中删除，本文件不保留兼容
- 所有页面路径使用复数形式（test-sets, runs, reports），保持 RESTful 风格
- `Navigate` 组件用于 `/rag-eval` 根路径自动跳转到测试集列表
