# 07 - 进度恢复 API Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 07 - 进度恢复 API

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

提供 REST API 端点，允许前端在 SSE 断线重连后查询当前测试运行进度。

## 端点定义

```
GET /api/runs/{run_id}/progress
```

## 响应格式

### 运行中

```json
{
  "run_id": "uuid-string",
  "status": "running",
  "current": 23,
  "total": 50,
  "percentage": 46.0,
  "last_case_result": {
    "case_id": "uuid-string",
    "query": "3岁儿童大肌肉发展迟缓的表现",
    "hit_at_1": true,
    "hit_at_3": true,
    "hit_at_5": true,
    "hit_rank": 1,
    "score": 0.85
  },
  "started_at": "2026-04-17T10:00:00Z",
  "elapsed_seconds": 138
}
```

> **注意**：运行中状态不包含 `validation_results`，因为校验阶段尚未开始。如果断线重连时校验已完成，`status` 将为 `completed`，此时响应包含 `validation_results`（见下方"已完成"格式）。

### 已完成

```json
{
  "run_id": "uuid-string",
  "status": "completed",
  "current": 50,
  "total": 50,
  "percentage": 100.0,
  "metrics": {
    "precision_at_1": 0.84,
    "precision_at_3": 0.78,
    "precision_at_5": 0.72,
    "mrr": 0.71,
    "ndcg_at_5": 0.79,
    "hit_rate_at_5": 0.96,
    "avg_latency_ms": 245
  },
  "validation_results": [
    {"layer": 1, "name": "基础检索质量", "status": "pass", "score": 0.84},
    {"layer": 2, "name": "领域覆盖度", "status": "warn", "score": 0.65}
  ],
  "report_id": "uuid-string",
  "started_at": "2026-04-17T10:00:00Z",
  "completed_at": "2026-04-17T10:03:00Z",
  "elapsed_seconds": 180
}
```

### 已失败

```json
{
  "run_id": "uuid-string",
  "status": "failed",
  "current": 23,
  "total": 50,
  "percentage": 46.0,
  "error": "LLM API 超时，重试 3 次后仍失败",
  "error_code": "LLM_TIMEOUT",
  "failed_at": "2026-04-17T10:02:15Z",
  "started_at": "2026-04-17T10:00:00Z"
}
```

## 实现代码

在 `backend/src/controller/rag_test_controller.py` 中新增：

```python
from fastapi import APIRouter, HTTPException
from src.core.redis_client import RedisClient
from src.models.test_case import TestRun
from src.core.database import db_session_factory
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import json

router = APIRouter(prefix="/api", tags=["rag-eval-runs"])

@router.get("/runs/{run_id}/progress")
async def get_run_progress(run_id: str):
    """获取测试运行进度（用于SSE断线重连后的状态恢复）
    优先从Redis缓存读取，降级到数据库查询
    """
    # 1. 优先读 Redis
    try:
        redis_client = RedisClient.get_client()
        cached = await redis_client.get(f"rag_eval:run_progress:{run_id}")
        if cached:
            return json.loads(cached)
    except Exception as e:
        logger.debug(f"Redis读取失败，降级到数据库: {e}")

    # 2. 降级到数据库
    async with db_session_factory() as session:
        result = await session.execute(
            select(TestRun).where(TestRun.id == run_id)
        )
        run = result.scalar_one_or_none()
        if not run:
            raise HTTPException(status_code=404, detail="运行记录不存在")

        response = {
            "run_id": run_id,
            "status": run.status,
            "current": run.completed_cases or 0,
            "total": run.total_cases,
            "percentage": round((run.completed_cases or 0) / run.total_cases * 100, 2) if run.total_cases > 0 else 0,
            "started_at": run.started_at.isoformat() if run.started_at else None,
        }

        if run.status == "completed":
            response["completed_at"] = run.completed_at.isoformat() if run.completed_at else None
            response["metrics"] = run.metrics or {}

        if run.status == "failed":
            response["error"] = run.error_message
            response["error_code"] = run.error_code

        return response
```

## 注意事项

- Redis 缓存 TTL 设置为 1 小时，避免长期占用内存
- 数据库查询时只查询 `TestRun` 主表，不 JOIN 结果表（性能考虑）
- `last_case_result` 仅在 Redis 缓存中提供，数据库查询不包含（需要额外查询结果表，成本高）
- 前端调用此 API 的频率应限制在断线重连时，不要轮询
