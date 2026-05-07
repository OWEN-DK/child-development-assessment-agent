"""批量测试运行器，使用 Semaphore 控制并发"""

import asyncio
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone

from src.core.config.cache import ConfigCache
from src.repository.rag_eval.test_run_repository import TestRunRepository
from src.repository.rag_eval.test_run_result_repository import TestRunResultRepository
from src.service.rag_eval.run.executor import TestCaseExecutor
from src.service.rag_eval.run.result_processor import ResultProcessor
from src.utils.logger import logger


class BatchTestRunner:
    """批量测试运行器，使用 asyncio.Semaphore 控制并发

    全局并发限制：通过类级别 Semaphore 限制同时运行的最大运行数，
    防止多个运行同时执行时 LLM API 被限流。
    """

    # 类级别全局信号量（延迟初始化，避免模块加载时读取配置）
    _global_semaphore: asyncio.Semaphore | None = None
    _global_sem_lock: asyncio.Lock = asyncio.Lock()
    # 当前正在运行的运行数
    _running_count: int = 0
    _running_count_lock: asyncio.Lock = asyncio.Lock()

    def __init__(
        self,
        executor: TestCaseExecutor,
        result_processor: ResultProcessor,
        test_run_repository: TestRunRepository,
        test_run_result_repository: TestRunResultRepository,
        config_cache: ConfigCache | None = None,
        sse_publisher=None,
        facade=None,
        on_complete: Callable[[str], Awaitable[None]] | None = None,
    ):
        self._executor = executor
        self._result_processor = result_processor
        self._run_repo = test_run_repository
        self._result_repo = test_run_result_repository
        self._config = config_cache or ConfigCache.get_instance()
        self._sse = sse_publisher
        self._facade = facade
        self._on_complete = on_complete

    async def _get_global_semaphore(self) -> asyncio.Semaphore:
        """获取或创建全局运行信号量（延迟初始化）"""
        if self._global_semaphore is None:
            async with self._global_sem_lock:
                if self._global_semaphore is None:
                    max_concurrent = self._config.get_int("rag.eval.run.max_concurrent_runs", 2)
                    self._global_semaphore = asyncio.Semaphore(max_concurrent)
        return self._global_semaphore

    def _reset_global_semaphore(self):
        """重置全局信号量（配置变更时调用）"""
        self._global_semaphore = None

    async def execute_run(
        self,
        run_id: str,
        test_cases: list,
        task_id: str = None,
        progress_callback=None,
        cancellation_event: asyncio.Event | None = None,
        task_type: str = None,
    ) -> None:
        """执行完整测试运行

        流程：
        1. 获取全局并发信号量（限制同时运行的最大运行数）
        2. 更新 run status → running
        3. SSE: run_started
        4. 获取单运行并发配置，Semaphore 控制
        5. 逐个提交执行（每个用例前检查取消信号）
        6. 聚合结果
        7. 更新 run status → completed

        支持通过 cancellation_event 协作取消，或通过 asyncio.Task.cancel() 硬取消。
        """
        channel = f"test_run:{run_id}" if task_id else None

        # 获取全局并发信号量，限制同时运行的最大运行数
        global_sem = await self._get_global_semaphore()
        async with global_sem:
            async with self._running_count_lock:
                BatchTestRunner._running_count += 1
                current_running = BatchTestRunner._running_count
            try:
                await self._execute_run_inner(
                    run_id, test_cases, task_id, current_running,
                    progress_callback, cancellation_event, task_type, channel)
            finally:
                async with self._running_count_lock:
                    BatchTestRunner._running_count -= 1

    async def _execute_run_inner(
        self,
        run_id: str,
        test_cases: list,
        task_id: str,
        current_running: int,
        progress_callback=None,
        cancellation_event: asyncio.Event | None = None,
        task_type: str = None,
        channel: str | None = None,
    ) -> None:
        """执行测试运行的内部实现（已持有全局信号量）"""
        try:
            # 清理旧结果（重新评估时防止旧数据混入指标计算）
            deleted = await self._result_repo.delete_by_run_id(run_id)
            if deleted > 0:
                logger.info(f"运行[{run_id}] 已清理 {deleted} 条旧结果")

            # 更新状态为 running（清除上次运行的残留字段）
            await self._run_repo.update(run_id, {
                "status": "running",
                "started_at": datetime.now(timezone.utc),
                "completed_at": None,
                "passed_test_cases": 0,
                "total_test_cases": len(test_cases),
            })

            total = len(test_cases)
            await self._push_event(channel, "run_started", {"run_id": run_id, "total_cases": total})

            # 读取并发配置
            concurrency = self._config.get_int("rag.eval.run.concurrency", 5)
            sem = asyncio.Semaphore(concurrency)

            # 已完成用例计数器（线程安全）
            completed_count = 0
            count_lock = asyncio.Lock()

            async def _run_one(case, index):
                nonlocal completed_count
                # 每个用例执行前检查取消信号
                if cancellation_event and cancellation_event.is_set():
                    return None
                try:
                    await self._push_event(channel, "case_started", {
                        "run_id": run_id,
                        "case_id": case.id,
                        "query": case.query,
                        "index": index,
                        "total": total,
                    })
                    result = await self._execute_with_semaphore(sem, case, run_id, current_running)
                    async with count_lock:
                        completed_count += 1
                        current_count = completed_count
                    if result:
                        await self._push_event(channel, "case_completed", {
                            "case_id": case.id,
                            "passed": result.passed,
                            "precision": result.precision,
                            "recall": result.recall,
                            "execution_time_ms": result.execution_time_ms,
                            "completed_count": current_count,
                            "total": total,
                        })
                    return result
                except Exception as e:
                    async with count_lock:
                        completed_count += 1
                        current_count = completed_count
                    await self._push_event(channel, "case_failed", {
                        "case_id": case.id,
                        "query": case.query,
                        "error": str(e),
                        "completed_count": current_count,
                        "total": total,
                    })
                    return None

            # 并发执行所有用例
            tasks = [
                asyncio.create_task(_run_one(case, i))
                for i, case in enumerate(test_cases)
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # 检查是否被取消（CancelledError 会自动传播，但协作取消需要显式检查）
            is_cancelled = cancellation_event and cancellation_event.is_set()

            # 聚合已完成的结果（取消时也聚合已有的部分结果）
            # aggregate() 从 DB 读取结果计算 passed 并写入 test_runs，返回通过数
            successful_count = sum(1 for r in results if r is not None and not isinstance(r, Exception))
            passed = 0
            if successful_count > 0:
                passed = await self._result_processor.aggregate(run_id)

            # 根据取消状态更新（不再覆盖 passed_test_cases，aggregate 已写入）
            failed = total - passed
            if is_cancelled:
                await self._run_repo.update(run_id, {
                    "status": "cancelled",
                    "completed_at": datetime.now(timezone.utc),
                })
                await self._push_event(channel, "run_cancelled", {
                    "run_id": run_id,
                    "completed_count": completed_count,
                    "total_count": total,
                })
            else:
                # 先更新状态为 completed，让前端立即看到完成状态并显示进度条
                await self._run_repo.update(run_id, {
                    "status": "completed",
                    "completed_at": datetime.now(timezone.utc),
                })
                await self._push_event(channel, "run_completed", {
                    "run_id": run_id,
                    "passed_count": passed,
                    "failed_count": failed,
                    "total_count": total,
                })

            # 触发后处理流水线（仅正常完成时）
            if not is_cancelled and self._on_complete:
                try:
                    await self._on_complete(run_id)
                except Exception as pipeline_err:
                    logger.warning(f"运行[{run_id}] 后处理流水线异常（不阻塞主流程）: {pipeline_err}", exc_info=True)

            # pipeline 完成后更新 completed_at，确保耗时包含指标计算+报告生成
            if not is_cancelled:
                await self._run_repo.update(run_id, {
                    "completed_at": datetime.now(timezone.utc),
                })

        except asyncio.CancelledError:
            # asyncio.Task.cancel() 触发的硬取消
            logger.info(f"测试运行[{run_id}] 被取消")
            await self._run_repo.update(run_id, {"status": "cancelled"})
            await self._push_event(channel, "run_cancelled", {"run_id": run_id})
            raise  # 重新抛出，让 AsyncTaskManager 处理取消状态
        except Exception as e:
            logger.error(f"测试运行[{run_id}] 整体失败: {e}", exc_info=True)
            await self._run_repo.update(run_id, {"status": "failed"})
            await self._push_event(channel, "run_failed", {"run_id": run_id, "error": str(e)})

    async def _execute_with_semaphore(
        self,
        sem: asyncio.Semaphore,
        case,
        run_id: str,
        current_running: int = 1,
    ):
        """带信号量控制的单用例执行

        动态超时：基础超时 × 当前并发运行数，防止多运行并发时超时过短。
        """
        # 闭包创建不涉及 I/O，移到信号量外避免占用并发槽位
        retrieval_fn, generation_fn = None, None
        if self._facade:
            retrieval_fn, generation_fn = self._facade.build_execution_functions()

        async with sem:
            # 动态超时：基础 300 秒 × 当前并发运行数
            base_timeout_ms = 300_000
            timeout_ms = base_timeout_ms * current_running

            return await self._executor.execute(
                test_case=case,
                run_id=run_id,
                retrieval_fn=retrieval_fn,
                generation_fn=generation_fn,
                timeout_ms=timeout_ms,
            )

    async def _push_event(self, channel: str | None, event_type: str, data: dict):
        """推送 SSE 事件（{type, data} 统一格式）"""
        if not channel or not self._sse:
            return
        try:
            from fastapi.encoders import jsonable_encoder
            payload = {"type": event_type, "data": data}
            safe_payload = jsonable_encoder(payload)
            await self._sse.publish(channel, safe_payload)
        except Exception as e:
            logger.warning(f"SSE 推送失败 [{event_type}]: {e}")

