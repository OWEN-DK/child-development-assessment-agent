"""批量测试运行器，使用 Semaphore 控制并发"""

import asyncio
import json
from collections.abc import Awaitable, Callable
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
        generation_service=None,
        on_complete: Callable[[str], Awaitable[None]] | None = None,
    ):
        self._executor = executor
        self._result_processor = result_processor
        self._run_repo = test_run_repository
        self._result_repo = test_run_result_repository
        self._config = config_cache or ConfigCache.get_instance()
        self._sse = sse_publisher
        self._retrieval = retrieval_service
        self._generation = generation_service
        self._on_complete = on_complete

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
        1. 更新 run status → running
        2. SSE: run_started
        3. 获取并发配置，Semaphore 控制
        4. 逐个提交执行（每个用例前检查取消信号）
        5. 聚合结果
        6. 更新 run status → completed

        支持通过 cancellation_event 协作取消，或通过 asyncio.Task.cancel() 硬取消。
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
                    result = await self._execute_with_semaphore(sem, case, run_id)
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
    ):
        """带信号量控制的单用例执行"""
        async with sem:
            timeout_ms = self._get_config_int("rag.eval.run.timeout_ms", 30000)

            # 暂存检索结果（含 content），供 generation_fn 闭包引用
            _retrieved_items: list[dict] = []

            retrieval_fn = None
            if self._retrieval:
                async def _retrieval(query, age, domain):
                    results = await self._retrieval.retrieve_knowledge(query, limit=5)
                    items = []
                    for r in (results or []):
                        if isinstance(r, dict):
                            items.append({"id": r.get("id", ""), "content": r.get("content", "")})
                        else:
                            items.append({"id": getattr(r, "id", "") or "", "content": getattr(r, "content", "") or ""})
                    _retrieved_items.clear()
                    _retrieved_items.extend(items)
                    return items
                retrieval_fn = _retrieval

            # 构建生成函数：基于检索到的文档内容调用 LLM 生成答案
            generation_fn = None
            if self._generation:
                async def _generation(query, retrieved_ids):
                    from src.core.prompts_fallback import (
                        ANSWER_GENERATION_SYSTEM_PROMPT,
                        ANSWER_GENERATION_USER_PROMPT,
                    )
                    from src.schemas.llm import LLMMessage, LLMRequest

                    # 从暂存的检索结果中提取内容
                    context = "\n\n".join(
                        item.get("content", "") for item in _retrieved_items if item.get("content")
                    )
                    if not context:
                        return None

                    model = self._get_config_str("rag.eval.run.generation_model", "qwen-plus")
                    user_prompt = ANSWER_GENERATION_USER_PROMPT.format(
                        query=query, context=context,
                    )
                    resp = await self._generation.chat(LLMRequest(
                        messages=[
                            LLMMessage(role="system", content=ANSWER_GENERATION_SYSTEM_PROMPT),
                            LLMMessage(role="user", content=user_prompt),
                        ],
                        model_name=model,
                        temperature=0.3,
                        max_tokens=2048,
                    ))
                    return resp.content
                generation_fn = _generation

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

    def _get_config_str(self, key: str, default: str) -> str:
        try:
            val = self._config.get(key)
            if val is not None:
                return str(val)
        except Exception:
            pass
        return default
