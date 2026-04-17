# 08 - 删除旧路由 /rag-evaluation Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 08 - 删除旧路由 /rag-evaluation

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

彻底删除旧的 `/rag-evaluation` 路由及相关组件，不保留任何向后兼容。

## 删除清单

### 前端文件

| 文件/目录 | 说明 |
|-----------|------|
| `frontend/src/features/rag-evaluation/` | 旧评估页面目录，整个目录删除 |
| `frontend/src/features/rag-evaluation/index.ts` | 旧导出文件 |
| `frontend/src/features/rag-evaluation/pages/RagEvaluationPage.tsx` | 旧主页面 |
| `frontend/src/features/rag-evaluation/components/` | 旧组件目录 |
| `frontend/src/features/rag-evaluation/hooks/useRagEvaluation.ts` | 旧状态管理 hook |
| `frontend/src/features/rag-evaluation/api/tuning.ts` | 旧 API 调用 |

### 路由配置

在 `frontend/src/router/index.tsx` 中删除：

```typescript
// 删除此行
{
  path: '/rag-evaluation',
  element: <RagEvaluationPage />,
}
```

### 菜单配置

在 `frontend/src/App.tsx` 的 `menuDataRender()` 中删除：

```typescript
// 删除此菜单项
{
  key: '/rag-evaluation',
  label: 'RAG 评估',
  icon: <ExperimentOutlined />,
}
```

### 后端路由（Phase-3 不删除，Phase 0 已修复后暂保留）

后端 `/rag/test/*` 路由在 Phase-3 暂不删除，因为新前端仍使用相同的 API 端点。后端路由的重构在后续 Phase 中按需进行。

## 验证步骤

1. 删除后运行 `npm run build` 确认无编译错误
2. 检查无残留 import 引用
3. 访问 `/rag-evaluation` 应返回 404（前端路由）
4. 确认 `/rag-eval/*` 新路由正常工作

## 注意事项

- 删除前确认新 `/rag-eval/*` 路由已完全替代旧功能
- 如有用户收藏了旧 URL，可在 Phase-3 完成后添加 301 重定向（可选）
- 删除操作不可逆，建议先创建 git 分支
