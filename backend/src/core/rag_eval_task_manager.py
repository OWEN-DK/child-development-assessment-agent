"""RAG评估专用任务管理器

组合SSEPublisher实现RAG评估特有的SSE事件。
不继承AsyncTaskManager，而是直接组合SSEPublisher。

注意：心跳由SSEPublisher.subscribe()的本地心跳循环负责，本类不管理心跳。
"""

import asyncio
import logging
from decimal import Decimal
from typing import Any, Awaitable, Callable, Optional

from fastapi.encoders import jsonable_encoder

from src.api.sse import SSEPublisher
from src.utils.logger import logger

logger = logging.getLogger(__name__)


class RagEvalTaskManager:
    """RAG评估专用任务管理器
    组合SSEPublisher实现RAG评估特有的SSE事件
    """

    _active_tasks: set = set()  # 保存后台任务强引用，防止GC后异常无法retrieve

    @classmethod
    async def start_test_run(
        cls, run_id: str, test_func: Callable[..., Awaitable[Any]], **kwargs
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
                await cls._publish(
                    channel,
                    "run_started",
                    {"run_id": run_id, **kwargs.get("start_metadata", {})},
                )

                # 2. 执行测试，注入进度回调
                async def progress_callback(
                    current: int, total: int, message: str, extra: Optional[dict] = None
                ):
                    await cls._publish(
                        channel,
                        "progress",
                        {
                            "run_id": run_id,
                            "current_case": current,
                            "total_cases": total,
                            "current_query": extra.get("current_query")
                            if extra
                            else None,
                            "elapsed_seconds": extra.get("elapsed_seconds")
                            if extra
                            else None,
                        },
                    )

                result = await test_func(
                    progress_callback=progress_callback,
                    **{k: v for k, v in kwargs.items() if k != "start_metadata"},
                )

                # 3. 发布 test_completed
                if result and "metrics" in result:
                    await cls._publish(
                        channel,
                        "test_completed",
                        {
                            "run_id": run_id,
                            "total_cases": result.get("total_cases", 0),
                            "passed_cases": result.get("passed_cases", 0),
                            "overall_metrics": result["metrics"],
                        },
                    )

                # 4. 发布 report_ready
                if result and "report_id" in result:
                    await cls._publish(
                        channel,
                        "report_ready",
                        {
                            "run_id": run_id,
                            "report_id": result["report_id"],
                            "report_url": f"/rag-eval/reports/{result['report_id']}",
                            "overall_metrics": result.get("metrics", {}),
                            "total_duration_seconds": result.get(
                                "total_duration_seconds", 0
                            ),
                            "validation_summary": result.get("validation_summary", {}),
                        },
                    )

                logger.info(f"RAG测试运行[{run_id}] 全部流程完成")

            except Exception as e:
                logger.error(f"RAG测试运行[{run_id}] 失败: {e}", exc_info=True)
                await cls._publish(
                    channel,
                    "run_failed",
                    {
                        "run_id": run_id,
                        "error_code": cls._classify_error(e),
                        "error_message": str(e),
                        "failed_at_case_id": kwargs.get("failed_at_case_id"),
                    },
                )

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
            safe_payload = jsonable_encoder(
                payload,
                custom_encoder={Decimal: lambda v: float(v)}
            )
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
