# 10 - SPA 回退路由 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 10 - SPA 回退路由

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

## 问题描述

前端使用 `BrowserRouter`（HTML5 History 模式），直接访问子路径（如 `/rag-eval/test-sets/abc123`）或刷新页面时，浏览器会向后端发送该路径的请求。如果后端没有对应的路由处理，将返回 404。

## 根因

```
用户访问 /rag-eval/test-sets/abc123
  ↓
浏览器发送 GET /rag-eval/test-sets/abc123 到后端
  ↓
后端无此路由 → 404
  ↓
用户看到空白页或错误页面
```

## 解决方案

在 FastAPI 后端配置 SPA 回退路由，将所有非 API 路径的 404 请求返回 `index.html`，由前端路由处理。

## 实施文件

`backend/src/server.py`

## 实现代码

在 `server.py` 中，所有 `include_router` 之后、`app.mount` 之前，添加回退路由：

```python
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

# ... 所有 router include 之后 ...

# SPA 回退路由：非 API 路径的 404 请求返回 index.html
FRONTEND_DIST_DIR = os.path.join(os.path.dirname(__file__), "../../frontend/dist")

@app.get("/{full_path:path}")
async def spa_fallback(full_path: str):
    """SPA回退路由
    将所有非API路径的请求返回index.html，由前端React Router处理路由
    """
    # API路径不走回退
    if full_path.startswith("api/") or full_path.startswith("docs") or full_path.startswith("openapi.json") or full_path.startswith("metrics"):
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Not Found")

    # 尝试返回静态文件
    file_path = os.path.join(FRONTEND_DIST_DIR, full_path)
    if os.path.isfile(file_path):
        return FileResponse(file_path)

    # 否则返回 index.html
    index_path = os.path.join(FRONTEND_DIST_DIR, "index.html")
    if os.path.isfile(index_path):
        return FileResponse(index_path)

    raise HTTPException(status_code=404, detail="Not Found")
```

## 路由优先级

FastAPI 路由匹配按注册顺序，因此回退路由必须**最后注册**：

```
1. include_router(task_controller)        # /api/tasks/*
2. include_router(rag_controller)          # /api/rag/*
3. include_router(rag_test_controller)     # /rag/test/*
4. include_router(config_controller)       # /api/config/*
5. include_router(config_health_controller)# /api/health/*
6. include_router(monitoring_controller)   # /api/monitoring/*
7. include_router(prompt_controller)       # /api/prompts/*
8. tuning_controller.register_routes(app)  # /api/tuning/*
9. app.mount("/metrics", metrics_app)      # /metrics/*
10. @app.get("/{full_path:path}")          # SPA 回退（最后）
```

## 开发环境处理

开发环境下（`npm run dev`），前端由 Vite 开发服务器提供，不需要后端回退。因此回退路由仅在生产环境（存在 `frontend/dist/index.html` 时）生效。

## 注意事项

- 静态文件（JS/CSS/图片）有真实文件，直接返回，不走回退
- API 路径（`/api/`、`/docs`、`/openapi.json`、`/metrics`）明确排除
- `full_path` 为空字符串时（即 `/` 路径），也返回 `index.html`
- 此方案与 CLAUDE.md 中"刷新 404 问题"的最佳实践一致
