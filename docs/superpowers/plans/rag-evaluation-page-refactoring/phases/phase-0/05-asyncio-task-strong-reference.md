# asyncio.create_task 强引用 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** asyncio.create_task 强引用

**Architecture:** 参考下方原文档的实现方案和数据模型

**Tech Stack:** Python, FastAPI, TypeScript, React

---

### Task 1: 实现核心逻辑与测试

**Files:**
- Modify: `backend/src/core/async_task.py`
- Modify: `backend/src/controller/rag_test_controller.py`
- Test: `backend/src/controller/rag_test_controller.py`

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

> **需求来源**: spec 文档 `01-phase-0-bug-fixes.md` 中 `2.0.1` 节
> **所属 Phase**: Phase 0
> **根因**: `asyncio.create_task()` 创建的任务没有强引用，可能被 GC 回收，导致任务静默终止

---

## 需求定义

当前 `AsyncTaskManager.start_task()` 和 `rag_test_controller.py` 中的 `_execute_with_progress` 都使用 `asyncio.create_task()` 创建后台任务，但没有保持对 Task 对象的强引用。

在 Python 的 asyncio 中，如果 Task 对象没有被引用，垃圾回收器可能会回收它，导致任务静默终止。长时间运行的任务（如批量测试，可能超过 10 分钟）更容易遇到此问题。

**修复要求**：
1. 所有通过 `asyncio.create_task()` 创建的后台任务必须保持强引用
2. 任务完成后自动清理引用，防止内存泄漏
3. 提供任务取消机制

---

## 验收标准

- [ ] 长时间任务（10min+）不会静默终止
- [ ] 任务完成后引用被正确清理
- [ ] 可通过 API 查询正在运行的任务列表

---

## 涉及文件

| 文件路径 | 操作 | 说明 |
|---------|------|------|
| `backend/src/core/async_task.py` | 修改 | `AsyncTaskManager` 增加任务追踪 |
| `backend/src/controller/rag_test_controller.py` | 修改 | 使用 `AsyncTaskManager` 替代直接 `create_task` |

---

## 实现方案

### 后端实现

**步骤 1：修改 `AsyncTaskManager` 增加任务追踪**

```python
# backend/src/core/async_task.py

import asyncio
import logging
import uuid
from typing import Optional, Callable
from datetime import datetime

logger = logging.getLogger(__name__)

class AsyncTaskManager:
    # 现有代码...
    
    # 新增：强引用集合，防止任务被 GC 回收
    _active_tasks: dict[str, asyncio.Task] = {}
    
    @classmethod
    async def start_task(
        cls,
        task_type: str,
        task_func: Callable,
        *args,
        progress_callback: Optional[Callable] = None,
        **kwargs
    ) -> str:
        """启动异步任务
        
        参数:
            task_type: 任务类型（用于 SSE 频道命名）
            task_func: 目标异步函数
            *args: 位置参数
            progress_callback: 进度回调（已废弃，改用 SSE）
            **kwargs: 关键字参数
            
        返回:
            task_id: 任务唯一标识
        """
        task_id = str(uuid.uuid4())
        channel = f"{task_type}:{task_id}"
        
        async def wrapped_task():
            try:
                logger.info(f'任务 {task_id} 开始执行')
                # 将 progress_callback 注入 kwargs，避免与位置参数冲突
                call_kwargs = {**kwargs}
                if progress_callback is not None:
                    call_kwargs['progress_callback'] = progress_callback
                result = await task_func(*args, **call_kwargs)
                safe_result = jsonable_encoder(result) if result is not None else {}
                await cls.publish_complete(task_type=task_type, task_id=task_id, result=safe_result)
                logger.info(f'任务 {task_id} 执行完成')
            except Exception as e:
                logger.error(f'任务 {task_id} 执行失败: {e}', exc_info=True)
                await cls.publish_error(task_type=task_type, task_id=task_id, error=str(e))
            finally:
                # 任务完成后自动清理引用
                cls._active_tasks.pop(task_id, None)
        
        # 创建任务并保持强引用
        task = asyncio.create_task(wrapped_task(), name=f"async-task-{task_id}")
        cls._active_tasks[task_id] = task
        
        # 添加任务完成回调（双重保险）
        task.add_done_callback(cls._on_task_done)
        
        return task_id
    
    @classmethod
    def _on_task_done(cls, task: asyncio.Task):
        """任务完成回调
        
        记录异常（如果有），并确保引用被清理。
        """
        task_id = None
        # 从 _active_tasks 中找到对应的 task_id
        for tid, t in cls._active_tasks.items():
            if t is task:
                task_id = tid
                break
        
        if task_id:
            if task.exception():
                logger.error(f'任务 {task_id} 抛出未捕获异常: {task.exception()}')
            # 清理引用（wrapped_task 的 finally 也会清理，这里是双重保险）
            cls._active_tasks.pop(task_id, None)
    
    @classmethod
    def get_active_tasks(cls) -> dict[str, dict]:
        """获取所有活跃任务信息
        
        返回:
            {task_id: {"name": str, "done": bool, "cancelled": bool}}
        """
        result = {}
        for task_id, task in cls._active_tasks.items():
            result[task_id] = {
                "name": task.get_name(),
                "done": task.done(),
                "cancelled": task.cancelled(),
            }
        return result
    
    @classmethod
    async def cancel_task(cls, task_id: str) -> bool:
        """取消指定任务
        
        参数:
            task_id: 任务 ID
            
        返回:
            是否成功取消
        """
        task = cls._active_tasks.get(task_id)
        if task and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                logger.info(f'任务 {task_id} 已取消')
                return True
        return False
```

**步骤 2：修改 `rag_test_controller.py` 使用 `AsyncTaskManager`**

找到 `run_tests` 端点中的 `asyncio.create_task()` 调用：

```python
# 修改前（约第 60 行）
asyncio.create_task(_execute_with_progress(run_id, request.concurrency))

# 修改后
from src.core.async_task import AsyncTaskManager

await AsyncTaskManager.start_task(
    task_type="test_run",
    task_func=_execute_with_progress,
    run_id=run_id,
    concurrency=request.concurrency,
)
```

**步骤 3：确保 `_execute_with_progress` 的签名匹配**

```python
# backend/src/controller/rag_test_controller.py

async def _execute_with_progress(run_id: str, concurrency: int = 5, progress_callback=None, **kwargs):
    """执行测试集并推送进度
    
    注意：此函数被 AsyncTaskManager.start_task 调用时，
    关键字参数必须与 start_task 的 kwargs 完全匹配。
    
    参数:
        run_id: 测试运行 ID
        concurrency: 并发数
        progress_callback: 进度回调（已废弃）
        **kwargs: 其他关键字参数
    """
    # ... 现有逻辑 ...
    # 如果原有代码使用 progress_callback，保留兼容性
    if progress_callback:
        # 旧版回调兼容
        pass
    
    # 使用 SSEPublisher 推送进度
    from src.api.sse import SSEPublisher
    channel = f"test_run:{run_id}"
    
    await SSEPublisher.publish(channel, {
        "type": "progress",
        "run_id": run_id,
        "message": "开始执行测试"
    })
    
    # ... 执行测试逻辑 ...
```

---

## 测试方案

### 单元测试

```python
# backend/tests/test_async_task.py

import pytest
import asyncio
from unittest.mock import AsyncMock, patch
from src.core.async_task import AsyncTaskManager

class TestAsyncTaskManager:
    @pytest.mark.asyncio
    async def test_task_strong_reference(self):
        """测试任务保持强引用"""
        async def dummy_task():
            await asyncio.sleep(0.1)
            return "done"
        
        task_id = await AsyncTaskManager.start_task(
            task_type="test",
            task_func=dummy_task,
        )
        
        # 任务应该在 _active_tasks 中
        assert task_id in AsyncTaskManager._active_tasks
        
        # 等待任务完成
        await asyncio.sleep(0.2)
        
        # 任务完成后应该被清理
        assert task_id not in AsyncTaskManager._active_tasks
    
    @pytest.mark.asyncio
    async def test_get_active_tasks(self):
        """测试获取活跃任务列表"""
        async def long_task():
            await asyncio.sleep(10)
        
        task_id = await AsyncTaskManager.start_task(
            task_type="test",
            task_func=long_task,
        )
        
        active = AsyncTaskManager.get_active_tasks()
        assert task_id in active
        assert active[task_id]["done"] is False
        
        # 清理
        await AsyncTaskManager.cancel_task(task_id)
    
    @pytest.mark.asyncio
    async def test_cancel_task(self):
        """测试取消任务"""
        async def long_task():
            await asyncio.sleep(10)
        
        task_id = await AsyncTaskManager.start_task(
            task_type="test",
            task_func=long_task,
        )
        
        result = await AsyncTaskManager.cancel_task(task_id)
        assert result is True
        assert task_id not in AsyncTaskManager._active_tasks
```

### 手动测试

1. 启动一个批量测试任务（128 用例）
2. 在任务执行期间，调用 `GET /api/tasks/active`（如新增此端点）查看活跃任务
3. 等待任务完成，确认没有 `Task exception was never retrieved` 警告
4. 在任务执行期间取消任务，确认正常终止

---

## 与 RagEvalTaskManager 的关系

**职责分工**（避免重复）：

| 特性 | AsyncTaskManager（现有） | RagEvalTaskManager（新增） |
|------|--------------------------|---------------------------|
| 用途 | 通用后台任务（文档导入、草稿生成等） | RAG评估专用任务 |
| 事件类型 | progress/complete/error（3种） | 10种RAG评估事件 |
| ID生成 | 内部生成UUID | 调用方预生成run_id |
| 心跳 | 无 | 内置15秒心跳 |
| 错误分类 | 无 | 5种错误码分类 |
| 使用场景 | 非RAG评估的异步任务 | RAG评估测试运行 |

**实施建议**：
- 文档导入、草稿生成等通用任务使用 `AsyncTaskManager`
- RAG 评估测试运行使用 `RagEvalTaskManager`
- 两者都保持强引用机制，防止 GC 问题

---

**返回索引：** [Phase 0 总览](../00-overview.md)
