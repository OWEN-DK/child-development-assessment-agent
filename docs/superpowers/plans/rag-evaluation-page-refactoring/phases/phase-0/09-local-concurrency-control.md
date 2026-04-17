# 本地并发控制替代分布式锁 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 本地并发控制替代分布式锁

**Architecture:** 参考下方原文档的实现方案和数据模型

**Tech Stack:** Python, FastAPI, TypeScript, React

---

### Task 1: 实现核心逻辑与测试

**Files:**
- Modify: `backend/src/service/rag_test_manager.py`
- Modify: `backend/src/core/distributed_lock.py`
- Test: `backend/src/service/rag_test_manager.py`

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

> **需求来源**: spec 文档 `01-phase-0-bug-fixes.md` 中 `2.0.2` 节
> **所属 Phase**: Phase 0
> **根因**: 分布式锁对唯一 run_id 无意义，增加复杂度；Redis 不可用时批量测试无法执行

---

## 需求定义

当前 `execute_batch` 方法使用 `DistributedLock` 保护整个批量测试执行。但由于 `run_id` 是唯一的，同一时刻不可能有两个进程执行同一个 run，分布式锁没有实际意义，反而增加了以下问题：

1. 依赖 Redis，Redis 不可用时批量测试无法执行
2. 锁超时时间（3600s）可能不够或过长
3. 增加代码复杂度和调试难度

**修复要求**：
1. 移除分布式锁，改用本地 `asyncio.Semaphore` 控制并发
2. 并发数通过参数传入，默认 5
3. Redis 不可用时不影响批量测试

---

## 验收标准

- [ ] 批量测试不依赖 Redis 锁
- [ ] 并发数可配置
- [ ] Redis 不可用时批量测试仍能执行

---

## 涉及文件

| 文件路径 | 操作 | 说明 |
|---------|------|------|
| `backend/src/service/rag_test_manager.py` | 修改 | 移除 DistributedLock，改用 asyncio.Semaphore |
| `backend/src/core/distributed_lock.py` | 检查 | 确认不再被批量测试引用 |

---

## 实现方案

### 后端实现

**步骤 1：修改 `execute_batch` 方法**

找到当前使用 `DistributedLock` 的代码：

```python
# 修改前
async def execute_batch(self, run_id: str, concurrency: int = 5, progress_callback=None):
    lock_name = f"rag:test_run:{run_id}"
    
    async def _execute_with_lock():
        # ... 实际执行逻辑
        pass
    
    await DistributedLock.execute_with_lock(lock_name, _execute_with_lock, timeout=3600)
```

替换为：

```python
# backend/src/service/rag_test_manager.py

import asyncio
import logging
from typing import Optional, Callable

logger = logging.getLogger(__name__)

class RagTestManager:
    async def execute_batch(
        self,
        run_id: str,
        concurrency: int = 5,
        progress_callback: Optional[Callable] = None,
    ) -> dict:
        """执行批量测试
        
        使用本地 Semaphore 控制并发，不依赖 Redis 分布式锁。
        
        参数:
            run_id: 测试运行 ID
            concurrency: 最大并发数，默认 5
            progress_callback: 进度回调（已废弃，改用 SSE）
            
        返回:
            聚合结果
        """
        from src.api.sse import SSEPublisher
        
        channel = f"test_run:{run_id}"
        
        # 获取测试用例列表
        test_cases = await self._get_test_cases_for_run(run_id)
        if not test_cases:
            raise ValueError(f"No test cases found for run {run_id}")
        
        total = len(test_cases)
        logger.info(f'开始批量测试 run={run_id}, total={total}, concurrency={concurrency}')
        
        # 推送开始事件
        await SSEPublisher.publish(channel, {
            "type": "batch_start",
            "run_id": run_id,
            "total": total,
            "concurrency": concurrency,
        })
        
        # 使用本地 Semaphore 控制并发
        semaphore = asyncio.Semaphore(concurrency)
        results = []
        errors = []
        completed_counter = {"count": 0}  # 使用 dict 作为可变容器，避免 nonlocal 竞态
        counter_lock = asyncio.Lock()  # 保护计数器
        
        async def execute_with_semaphore(test_case: dict) -> Optional[dict]:
            async with semaphore:
                try:
                    # 推送用例开始事件
                    await SSEPublisher.publish(channel, {
                        "type": "case_start",
                        "case_id": test_case.get('id'),
                        "query": test_case.get('query'),
                        "completed": completed_counter["count"],
                        "total": total,
                    })
                    
                    result = await self._execute_single_test_case(test_case)
                    
                    # 使用锁保护计数器，避免竞态条件
                    async with counter_lock:
                        completed_counter["count"] += 1
                        current_completed = completed_counter["count"]
                    
                    # 推送进度事件
                    progress = (current_completed / total) * 100
                    await SSEPublisher.publish(channel, {
                        "type": "progress",
                        "run_id": run_id,
                        "progress": progress,
                        "completed": current_completed,
                        "total": total,
                        "current_case": test_case.get('query'),
                    })
                    
                    # 推送用例完成事件
                    await SSEPublisher.publish(channel, {
                        "type": "case_complete",
                        "case_id": test_case.get('id'),
                        "status": result.get('status', 'passed'),
                        "result": result,
                        "completed": current_completed,
                        "total": total,
                    })
                    
                    return result
                except Exception as e:
                    async with counter_lock:
                        completed_counter["count"] += 1
                        current_completed = completed_counter["count"]
                    
                    error_info = {
                        "case_id": test_case.get('id'),
                        "error": str(e),
                    }
                    errors.append(error_info)
                    logger.error(f'用例执行失败 case_id={test_case.get("id")}: {e}', exc_info=True)
                    
                    await SSEPublisher.publish(channel, {
                        "type": "case_error",
                        **error_info,
                        "completed": current_completed,
                        "total": total,
                    })
                    return None
        
        # 并发执行所有用例
        tasks = [execute_with_semaphore(tc) for tc in test_cases]
        raw_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 处理异常结果
        for i, raw in enumerate(raw_results):
            if isinstance(raw, Exception):
                errors.append({
                    "case_id": test_cases[i].get('id'),
                    "error": str(raw),
                })
            elif raw is not None:
                results.append(raw)
        
        # 等待所有结果聚合（需求点 10）
        aggregation = await self._aggregate_results(run_id, results, errors, total)
        
        # 推送完成事件
        await SSEPublisher.publish(channel, {
            "type": "batch_complete",
            "run_id": run_id,
            "total": total,
            "completed": len(results),
            "failed": len(errors),
            "aggregation": aggregation,
        })
        
        return aggregation
```

**步骤 2：移除 DistributedLock 相关导入**

```python
# 删除以下导入（如不再被其他代码使用）
# from src.core.distributed_lock import DistributedLock
```

**步骤 3：确认 `DistributedLock` 是否还被其他代码使用**

```bash
grep -r "DistributedLock" backend/src/
```

如果只有 `rag_test_manager.py` 使用，可以保留 `DistributedLock` 类（未来可能有用），但不再在批量测试中使用。

---

## 测试方案

### 单元测试

```python
# backend/tests/test_local_concurrency.py

import pytest
import asyncio
from unittest.mock import AsyncMock, patch

class TestLocalConcurrency:
    @pytest.mark.asyncio
    async def test_semaphore_concurrency(self):
        """测试 Semaphore 正确控制并发"""
        manager = RagTestManager()
        
        concurrent_count = 0
        max_concurrent = 0
        lock = asyncio.Lock()
        
        async def mock_execute(test_case):
            nonlocal concurrent_count, max_concurrent
            async with lock:
                concurrent_count += 1
                max_concurrent = max(max_concurrent, concurrent_count)
            
            await asyncio.sleep(0.1)  # 模拟耗时操作
            
            async with lock:
                concurrent_count -= 1
            
            return {"status": "passed"}
        
        test_cases = [{"id": f"case-{i}", "query": f"query {i}"} for i in range(10)]
        
        with patch.object(manager, '_get_test_cases_for_run', return_value=test_cases):
            with patch.object(manager, '_execute_single_test_case', side_effect=mock_execute):
                with patch.object(manager, '_aggregate_results', return_value={}):
                    await manager.execute_batch("run-1", concurrency=3)
        
        # 最大并发数不应超过 3
        assert max_concurrent <= 3
    
    @pytest.mark.asyncio
    async def test_no_redis_dependency(self):
        """测试批量测试不依赖 Redis"""
        manager = RagTestManager()
        
        test_cases = [{"id": "case-1", "query": "query 1"}]
        
        with patch.object(manager, '_get_test_cases_for_run', return_value=test_cases):
            with patch.object(manager, '_execute_single_test_case', return_value={"status": "passed"}):
                with patch.object(manager, '_aggregate_results', return_value={}):
                    # 即使 Redis 不可用，也不应抛出异常
                    result = await manager.execute_batch("run-1", concurrency=1)
        
        assert result is not None
```

### 手动测试

1. 停止 Redis 服务
2. 创建一个包含 20 个用例的测试集
3. 执行批量测试，并发数设为 5
4. 确认测试正常执行，不报 Redis 相关错误
5. 检查日志，确认最大并发数不超过 5

---

## 注意事项

1. **单实例限制**：`asyncio.Semaphore` 只在单个进程内有效。多实例部署时，每个实例独立控制并发。如果需要全局并发限制，仍需分布式锁。但当前场景下 `run_id` 唯一，不存在并发执行同一 run 的情况。
2. **Semaphore vs Lock**：`Semaphore(n)` 允许最多 n 个协程同时执行，`Lock` 只允许 1 个。此处使用 Semaphore 是正确的。
3. **return_exceptions=True**：`asyncio.gather` 必须设置 `return_exceptions=True`，否则单个用例失败会导致整个批量测试失败。
4. **进度推送**：每个用例开始/完成时都推送 SSE 事件，前端据此更新进度条。

---

**返回索引：** [Phase 0 总览](../00-overview.md)
