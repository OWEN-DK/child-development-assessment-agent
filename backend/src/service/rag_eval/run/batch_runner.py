"""批量测试运行器，使用 Semaphore 控制并发"""

import asyncio
import json
from datetime import datetime, timezone

from src.core.config.cache import ConfigCache
from src.core.interfaces import IRetrievalService
from src.repository.rag_eval.test_run_repository import TestRunRepository
from src.repository.rag_eval.test_run_result_repository import TestRunResultRepository
from src.service.rag_eval.run.executor import TestCaseExecutor
from src.service.rag_eval.run.result_processor import ResultProcessor
from src.utils.logger import logger


class BatchTestRunner:
    """批量测试运行器，使用 asyncio.Semaphore 控制并发"""

    def __init__(
        self,
        executor: TestCaseExecutor,
        result_processor: ResultProcessor,
        test_run_repository: TestRunRepository,
        test_run_result_repository: TestRunResultRepository,
        config_cache: ConfigCache | None = None,
        sse_publisher=None,
        retrieval_service: IRetrievalService | None = None,
    ):
        self._executor = executor
        self._result_processor = result_processor
        self._run_repo = test_run_repository
        self._result_repo = test_run_result_repository
        self._config = config_cache or ConfigCache.get_instance()
        self._sse = sse_publisher
        self._retrieval = retrieval_service

    async def execute_run(
        self,
        run_id: str,
        test_cases: list,
        task_id: str = None,
        progress_callback=None,
        cancellation_event=None,
        task_type: str = None,
    ) -> None:
        """执行完整测试运行

        流程：
        1. 更新 run status → running
        2. SSE: run_started
        3. 获取并发配置，Semaphore 控制
        4. 逐个提交执行
        5. 聚合结果
        6. 更新 run status → completed
        """
        channel = f"test_run:{run_id}" if task_id else None

        try:
            # 更新状态为 running
            await self._run_repo.update(run_id, {
                "status": "running",
                "started_at": datetime.now(timezone.utc),
                "total_test_cases": len(test_cases),
            })

            total = len(test_cases)
            await self._push_event(channel, "run_started", {"run_id": run_id, "total_cases": total})

            # 读取并发配置
            concurrency = self._get_config_int("rag.eval.run.concurrency", 3)
            sem = asyncio.Semaphore(concurrency)

            async def _run_one(case, index):
                try:
                    await self._push_event(channel, "case_started", {
                        "run_id": run_id,
                        "case_id": case.id,
                        "query": case.query,
                        "index": index,
                        "total": total,
                    })
                    result = await self._execute_with_semaphore(sem, case, run_id)
                    if result:
                        await self._push_event(channel, "case_completed", {
                            "case_id": case.id,
                            "passed": result.passed,
                            "precision": result.precision,
                            "recall": result.recall,
                            "execution_time_ms": result.execution_time_ms,
                        })
                    return result
                except Exception as e:
                    await self._push_event(channel, "case_failed", {
                        "case_id": case.id,
                        "query": case.query,
                        "error": str(e),
                    })
                    return None

            # 并发执行所有用例
            tasks = [
                asyncio.create_task(_run_one(case, i))
                for i, case in enumerate(test_cases)
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # 聚合结果
            await self._result_processor.aggregate(run_id)

            # 更新状态为 completed
            passed = sum(1 for r in results if r and getattr(r, "passed", False))
            failed = total - passed
            await self._run_repo.update(run_id, {
                "status": "completed",
                "completed_at": datetime.now(timezone.utc),
                "passed_test_cases": passed,
            })

            await self._push_event(channel, "run_completed", {
                "run_id": run_id,
                "passed_count": passed,
                "failed_count": failed,
                "total_count": total,
            })

        except Exception as e:
            logger.error(f"测试运行[{run_id}] 整体失败: {e}", exc_info=True)
            await self._run_repo.update(run_id, {"status": "failed"})
            await self._push_event(channel, "run_failed", {"run_id": run_id, "error": str(e)})

    async def _execute_with_semaphore(
        self,
        sem: asyncio.Semaphore,
        case,
        run_id: str,
    ):
        """带信号量控制的单用例执行"""
        async with sem:
            timeout_ms = self._get_config_int("rag.eval.run.timeout_ms", 30000)

            retrieval_fn = None
            if self._retrieval:
                async def _retrieval(query, age, domain):
                    results = await self._retrieval.retrieve_knowledge(query, limit=5)
                    return [{"id": getattr(r, "id", "") or r.get("id", "")} for r in (results or [])]
                retrieval_fn = _retrieval

            generation_fn = None

            return await self._executor.execute(
                test_case=case,
                run_id=run_id,
                timeout_ms=timeout_ms,
                retrieval_fn=retrieval_fn,
                generation_fn=generation_fn,
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

    def _get_config_int(self, key: str, default: int) -> int:
        try:
            val = self._config.get(key)
            if val is not None:
                return int(val)
        except Exception:
            pass
        return default
