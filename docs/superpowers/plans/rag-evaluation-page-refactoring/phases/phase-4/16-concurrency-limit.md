# 16 - 并发限制 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 16 - 并发限制

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

> **需求来源**: spec 文档 `05-validation-layers.md` 中 `3.3 校验层定义` 节
> **所属 Phase**: Phase 4

## 需求定义

同一时间最多允许 3 个 TestReport 的校验引擎并行执行，超出请求进入队列等待。队列上限 10，超出返回 503 错误。

> **重要**: 此并发限制是 **report 级别**的，不是 layer 级别。单个 TestReport 内部的 6 层校验子层（如 Layer 4a/4b/4c/5a/5b/5c）可以全部并行执行，不受此限制。Semaphore 控制的是同时有多少个 TestReport 在校验，不是单个报告内部有多少子层在并行。

> **注意**: 并发核心逻辑已在 `01-validation-orchestrator.md` 中实现，本文档补充策略细节。

## 验收标准

- [ ] 最多 3 个并行校验
- [ ] 队列上限 10
- [ ] 超出队列返回 503
- [ ] 使用 asyncio.Semaphore 控制并发

## 并发控制策略

### 实现机制

```python
# backend/src/core/validation/orchestrator.py (核心实现)

MAX_CONCURRENT_REPORTS = 3
QUEUE_MAX = 10

class ValidationOrchestrator:
    _semaphore: asyncio.Semaphore | None = None
    
    @classmethod
    def init(cls, max_concurrent: int = MAX_CONCURRENT_REPORTS):
        cls._semaphore = asyncio.Semaphore(max_concurrent)
    
    async def execute(self, db, test_run):
        if not self._semaphore:
            self.init()
        
        # 等待信号量，超时 5s 返回 503
        try:
            await asyncio.wait_for(self._semaphore.acquire(), timeout=5)
        except asyncio.TimeoutError:
            raise HTTPException(status_code=503, detail="校验队列已满，请稍后重试")
        
        try:
            return await self._execute_with_timeout(db, test_run)
        finally:
            self._semaphore.release()
```

### 并发流程图

```
请求到达
    │
    ├── Semaphore 有空位? ── Yes ──▶ 执行校验
    │
    └── No
         │
         ├── 等待 ≤ 5s 有空位? ── Yes ──▶ 执行校验
         │
         └── No (超时) ──▶ 返回 503 "校验队列已满"
```

### API 路由

```python
# backend/src/api/validation_routes.py
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from src.core.validation.orchestrator import ValidationOrchestrator

router = APIRouter(prefix="/api/validation", tags=["validation"])

@router.post("/run/{test_run_id}")
async def run_validation(test_run_id: str, db: AsyncSession = Depends(get_db)):
    """触发校验引擎"""
    test_run = await get_test_run(db, test_run_id)
    if not test_run:
        raise HTTPException(status_code=404, detail="TestRun 不存在")
    
    orchestrator = ValidationOrchestrator()
    try:
        report = await orchestrator.execute(db, test_run)
        return {"report_id": report.id, "status": report.status}
    except HTTPException as e:
        if e.status_code == 503:
            raise
        raise
```

## 测试方案

```python
@pytest.mark.asyncio
async def test_concurrent_limit():
    """最多 3 个并行校验"""
    ...

@pytest.mark.asyncio
async def test_queue_overflow():
    """超出队列返回 503"""
    ...
```

## 注意事项

- 使用 `asyncio.Semaphore` 控制并发，不使用分布式锁
- 队列等待超时 5s 后返回 503
- 本地并发控制替代分布式锁（CLAUDE.md 要求）
- 核心实现见 `01-validation-orchestrator.md`
