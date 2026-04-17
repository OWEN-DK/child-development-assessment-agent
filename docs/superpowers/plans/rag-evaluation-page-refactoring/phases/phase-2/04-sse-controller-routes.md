# 04 - SSE 控制器路由 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 04 - SSE 控制器路由

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

## SSE 端点全链映射表（Phase 0-2 统一）

> 此表为所有 Phase 的 SSE 端点唯一真相源，各 Phase 文档必须引用此表。
> **端点前缀**: 以 spec 为准，统一使用 `/api/` 前缀。

| Phase | 端点路径 | 用途 | 频道格式 | 状态 |
|-------|----------|------|----------|------|
| Phase-0（旧） | `/rag/test/run/{run_id}/stream` | 旧测试运行 SSE | `test_run:{run_id}` | Phase-3 删除 |
| Phase-0（现有） | `/rag/test/drafts/generate/{task_id}/stream` | 草稿生成 SSE | `draft_generation:{task_id}` | 保留 |
| Phase-2（新增） | `/api/runs/{run_id}/sse` | 新测试运行 SSE | `test_run:{run_id}` | Phase-2 新增，替代旧端点 |
| Phase-2（新增） | `/api/sse/exports` | 导出任务 SSE | `exports:{user_id}` | Phase-2 新增 |

**前端 URL 构建规则**（适用于所有 Phase）：
```typescript
// 根据 channel 前缀映射到实际端点
if (channel.startsWith('test_run:')) {
  const runId = channel.split(':')[1];
  url = `${apiBaseUrl}/api/runs/${runId}/sse`;  // Phase-2+ (spec 标准)
} else if (channel.startsWith('draft_generation:')) {
  const taskId = channel.split(':')[1];
  url = `${apiBaseUrl}/rag/test/drafts/generate/${taskId}/stream`;
} else if (channel.startsWith('exports:')) {
  const userId = channel.split(':')[1];
  url = `${apiBaseUrl}/api/sse/exports?user_id=${userId}`;
}
```

## 路由定义

在 `backend/src/controller/rag_test_controller.py` 中新增/修改以下 SSE 相关路由。

## 路由清单

| 方法 | 路径 | 说明 | 频道格式 |
|------|------|------|----------|
| GET | `/api/runs/{run_id}/sse` | 测试运行 SSE 流 | `test_run:{run_id}` |
| GET | `/api/sse/exports` | 导出任务 SSE 流 | `exports:{user_id}` |

## 实现代码

### 1. 测试运行 SSE 端点

```python
from fastapi import APIRouter, Query
from src.api.sse import sse_response

# 注意：此 router 使用 /api 前缀，与 spec 保持一致
router = APIRouter(prefix="/api", tags=["rag-eval-sse"])

@router.get("/runs/{run_id}/sse")
async def get_test_run_sse(run_id: str):
    """获取测试运行的SSE实时推送流
    前端通过EventSource连接此端点，接收测试进度、用例结果、校验状态等事件
    """
    return sse_response(f"test_run:{run_id}")
```

### 2. 导出 SSE 端点

```python
@router.get("/sse/exports")
async def get_export_sse(user_id: str = Query(..., description="用户标识")):
    """获取导出任务的SSE实时推送流
    独立于测试运行的SSE通道，用于推送PDF/CSV导出完成事件
    """
    return sse_response(f"exports:{user_id}")
```

## 与现有路由的关系

现有路由：
- `GET /rag/test/run/{run_id}/stream` — 旧 SSE 端点

**处理方式**：Phase-3 删除旧路由时一并清理，不保留兼容。

## 注意事项

- `user_id` 参数在 Phase-2 阶段可临时使用固定值或 session 标识，Phase-5 接入认证后替换为真实用户 ID
- SSE 端点返回 `StreamingResponse`，不会被 FastAPI 的中间件拦截处理
- 确保 Nginx 等反向代理配置了 `proxy_buffering off` 和合理的 `proxy_read_timeout`（建议 ≥ 60 秒）
- **端点前缀**: 新增 SSE 端点统一使用 `/api/` 前缀（与 spec 一致），与旧端点 `/rag/test/` 前缀区分
