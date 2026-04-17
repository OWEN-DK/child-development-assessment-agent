# 02 - RagEvalTaskManager 实现 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 02 - RagEvalTaskManager 实现

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

## 现状分析

现有 `AsyncTaskManager` 位于 `backend/src/core/async_task.py`，已具备基础能力：
- 生成 UUID task_id，包装业务函数执行
- 内置 `progress_callback` 默认推送 SSE 进度
- 统一处理异常和完成消息，使用 `jsonable_encoder` 序列化

## 需要增强的内容

现有实现仅支持通用 `progress/complete/error` 三种消息类型。Phase-2 需要支持 RAG 评估特有的 SSE 事件类型。

## 实施方案

### 方案选择：组合而非继承

**为什么**：现有 `AsyncTaskManager` 是通用组件，被多处引用（文档导入、草稿生成等）。`RagEvalTaskManager` 不继承它，而是直接组合 `SSEPublisher`，因为 RAG 评估需要自定义的事件类型，继承反而增加不必要的耦合。

### 新增文件

`backend/src/core/rag_eval_task_manager.py`

### 核心设计

```python
import asyncio
import logging
from typing import Optional, Any, Callable, Awaitable
from fastapi.encoders import jsonable_encoder
from src.api.sse import SSEPublisher
from src.utils.logger import logger

logger = logging.getLogger(__name__)


class RagEvalTaskManager:
    """RAG评估专用任务管理器
    组合SSEPublisher实现RAG评估特有的SSE事件

    注意：心跳由SSEPublisher.subscribe()的本地心跳循环负责，本类不管理心跳。
    """

    _active_tasks: set = set()  # 保存后台任务强引用，防止GC后异常无法retrieve

    @classmethod
    async def start_test_run(
        cls,
        run_id: str,
        test_func: Callable[..., Awaitable[Any]],
        **kwargs
    ) -> str:
        """启动测试运行任务
        Args:
            run_id: 测试运行ID（由调用方预生成，非本方法生成）
            test_func: 实际测试执行函数
            **kwargs: 传递给test_func的参数
        Returns:
            run_id: 返回传入的运行ID
        """
        channel = f"test_run:{run_id}"

        async def wrapped_task():
            try:
                # 1. 发布 run_started
                await cls._publish(channel, "run_started", {
                    "run_id": run_id,
                    **kwargs.get("start_metadata", {})
                })

                # 2. 执行测试，注入进度回调
                async def progress_callback(current: int, total: int, message: str, extra: Optional[dict] = None):
                    await cls._publish(channel, "progress", {
                        "run_id": run_id,
                        "current_case": current,
                        "total_cases": total,
                        "current_query": extra.get("current_query") if extra else None,
                        "elapsed_seconds": extra.get("elapsed_seconds") if extra else None,
                    })

                result = await test_func(
                    progress_callback=progress_callback,
                    **{k: v for k, v in kwargs.items() if k != "start_metadata"}
                )

                # 3. 发布 test_completed
                if result and "metrics" in result:
                    await cls._publish(channel, "test_completed", {
                        "run_id": run_id,
                        "total_cases": result.get("total_cases", 0),
                        "passed_cases": result.get("passed_cases", 0),
                        "overall_metrics": result["metrics"]
                    })

                # 4. 发布 report_ready
                if result and "report_id" in result:
                    await cls._publish(channel, "report_ready", {
                        "run_id": run_id,
                        "report_id": result["report_id"],
                        "report_url": f"/rag-eval/reports/{result['report_id']}",
                        "overall_metrics": result.get("metrics", {}),
                        "total_duration_seconds": result.get("total_duration_seconds", 0),
                        "validation_summary": result.get("validation_summary", {})
                    })

                logger.info(f"RAG测试运行[{run_id}] 全部流程完成")

            except Exception as e:
                logger.error(f"RAG测试运行[{run_id}] 失败: {e}", exc_info=True)
                await cls._publish(channel, "run_failed", {
                    "run_id": run_id,
                    "error_code": cls._classify_error(e),
                    "error_message": str(e),
                    "failed_at_case_id": kwargs.get("failed_at_case_id")
                })

        # 启动后台任务，保存强引用防止 GC 后异常无法 retrieve
        task = asyncio.create_task(wrapped_task())
        cls._active_tasks.add(task)
        task.add_done_callback(cls._active_tasks.discard)
        return run_id

    @classmethod
    async def _publish(cls, channel: str, event_type: str, data: dict):
        """统一事件发布入口，确保jsonable_encoder处理"""
        payload = {"type": event_type, **data}
        try:
            safe_payload = jsonable_encoder(payload)
        except Exception as e:
            logger.error(f"SSE事件序列化失败 [{event_type}]: {e}")
            safe_payload = {"type": event_type, "error": "序列化失败"}
        await SSEPublisher.publish(channel, safe_payload)

    @classmethod
    def _classify_error(cls, error: Exception) -> str:
        """错误分类"""
        error_msg = str(error).lower()
        if "timeout" in error_msg:
            return "LLM_TIMEOUT"
        if "connection" in error_msg or "refused" in error_msg:
            return "CONNECTION_ERROR"
        if "rate limit" in error_msg or "429" in error_msg:
            return "RATE_LIMITED"
        if "invalid" in error_msg or "format" in error_msg:
            return "INVALID_RESPONSE"
        return "UNKNOWN_ERROR"
```

## 与现有 AsyncTaskManager 的关系

| 特性 | AsyncTaskManager（现有） | RagEvalTaskManager（新增） |
|------|--------------------------|---------------------------|
| 用途 | 通用后台任务 | RAG评估专用 |
| 事件类型 | progress/complete/error | RAG评估业务事件 |
| ID生成 | 内部生成UUID | 调用方预生成run_id |
| 心跳 | 无 | 由SSEPublisher.subscribe()负责 |
| 错误分类 | 无 | 5种错误码分类 |

## 注意事项

- `run_id` 由调用方预生成，因为需要在启动任务前就写入数据库记录
- 心跳由 `SSEPublisher.subscribe()` 的本地心跳循环负责，每个SSE连接独立心跳，`RagEvalTaskManager` 不管理心跳
- 校验事件（validation_started/validation_completed）由 Phase 4 的 ValidationOrchestrator 自行发布，不在本类中硬编码
- 所有发布方法内部统一使用 `jsonable_encoder`，调用方无需关心序列化
