# System Config Page Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Register the existing `SystemConfigPage` to the application router and remove the partial configuration panel from the RAG evaluation page.

**Architecture:** We are updating the React Router configuration in `router/index.tsx` and adding a new menu link in the `ProLayout` of `App.tsx`. We will also refactor `RagEvaluationPage.tsx` to remove `ConfigTuningPanel` and finally delete `ConfigTuningPanel.tsx` since it's no longer needed.

**Tech Stack:** React, React Router DOM, Ant Design ProComponents

---

## Chunk 1: Router and Navigation Setup

### Task 1: Add SystemConfigPage to Router

**Files:**
- Modify: `frontend/src/router/index.tsx`

- [ ] **Step 1: Import the page and add route**
  - Import `SystemConfigPage` from `../pages/SystemConfigPage`.
  - Add `{ path: 'system-config', element: <SystemConfigPage /> }` to the children array of the root route.

- [ ] **Step 2: Verify compilation**
  - Run `npm run build` or check for TS errors.

### Task 2: Add Navigation Link

**Files:**
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Update menuDataRender**
  - Add `{ path: '/system-config', name: '系统配置' }` to the `menuDataRender` array in `ProLayout`.

- [ ] **Step 2: Verify compilation**
  - Run `npm run build` or check for TS errors.

---

## Chunk 2: Clean up RAG Evaluation Page

### Task 3: Remove ConfigTuningPanel from RagEvaluationPage

**Files:**
- Modify: `frontend/src/features/rag-evaluation/pages/RagEvaluationPage.tsx`

- [ ] **Step 1: Remove imports and usage**
  - Remove `import { ConfigTuningPanel } from '../components/ConfigTuningPanel';`.
  - Remove the `<div className={styles.rightPanel}>...</div>` block.
  - Update any layout classes if necessary (the left panel should now take full width).

- [ ] **Step 2: Verify compilation**
  - Run `npm run build` or check for TS errors.

### Task 4: Delete ConfigTuningPanel Component

**Files:**
- Delete: `frontend/src/features/rag-evaluation/components/ConfigTuningPanel.tsx`
- Delete: `frontend/src/features/rag-evaluation/components/ConfigTuningPanel.module.scss` (if exists)

- [ ] **Step 1: Delete files**
  - Use `rm` or `DeleteFile` tool.

- [ ] **Step 2: Commit**
  - `git add frontend/src/router/index.tsx frontend/src/App.tsx frontend/src/features/rag-evaluation/pages/RagEvaluationPage.tsx`
  - `git rm frontend/src/features/rag-evaluation/components/ConfigTuningPanel*`
  - `git commit -m "feat: migrate to dedicated system config page"`
