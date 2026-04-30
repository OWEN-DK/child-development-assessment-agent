"""TraceWriter - 异步队列写入追踪数据

采用独立队列异步写入追踪数据，不阻塞主流程。
支持采样策略、批量写入、队列满降级。
"""

import asyncio
import logging
import random
import time
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from src.core.database import async_session_factory
from src.core.tracing.cost import calculate_cost
from src.core.tracing.truncation import (save_full_content, truncate_content,
                                         truncate_messages)
from src.models.monitor import CallLevel, LLMCallLog
from src.models.trace import Trace, TraceStatus

logger = logging.getLogger(__name__)

_default_writer: "TraceWriter | None" = None


def get_trace_writer() -> "TraceWriter":
    """获取 TraceWriter 单例实例"""
    global _default_writer
    if _default_writer is None:
        _default_writer = TraceWriter()
    return _default_writer


def reset_trace_writer() -> None:
    """重置 TraceWriter 单例 (仅用于测试)"""
    global _default_writer
    _default_writer = None


class TraceWriter:
    def __init__(
        self,
        max_queue_size: int = 10000,
        sample_rate: float = 1.0,
        error_sample_rate: float = 1.0,
        batch_size: int = 100,
        flush_interval: float = 1.0,
    ):
        self.queue: asyncio.Queue = asyncio.Queue(maxsize=max_queue_size)
        self.sample_rate = sample_rate
        self.error_sample_rate = error_sample_rate
        self.batch_size = batch_size
        self.flush_interval = flush_interval
        self._task: asyncio.Task | None = None
        self._running = False

    async def start(self):
        """启动后台消费者"""
        if getattr(self, '_ever_started', False):
            logger.debug("TraceWriter 已初始化过，跳过重复启动")
            return
        self._ever_started = True
        self._running = True
        self._task = asyncio.create_task(self._consumer())
        logger.info("TraceWriter 后台消费者已启动")

    async def stop(self):
        """停止后台消费者"""
        self._running = False
        if self._task:
            # 等待队列排空 (最多 5 秒)
            try:
                while not self.queue.empty():
                    await asyncio.wait_for(self.queue.join(), timeout=5.0)
                    break
            except asyncio.TimeoutError:
                logger.warning("Queue drain timeout, forcing stop")
            except asyncio.QueueEmpty:
                pass

            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("TraceWriter 后台消费者已关闭")

    def _should_sample(self, is_error: bool = False) -> bool:
        """采样决策"""
        if is_error:
            return random.random() < self.error_sample_rate
        return random.random() < self.sample_rate

    def _ensure_started(self):
        """确保后台消费者已启动"""
        if not self._running:
            self._running = True
            self._task = asyncio.create_task(self._consumer())

    async def record_trace_start(
        self, trace_id: str, name: str, metadata: dict, start_time: datetime
    ):
        """记录 Trace 开始 (自动由 trace_context 调用)

        Trace 记录不受采样率影响，确保工作流完整性可追踪。
        """
        self._ensure_started()
        item = {
            "type": "trace_start",
            "trace_id": trace_id,
            "name": name,
            "metadata": metadata,
            "start_time": start_time,
            "timestamp": datetime.now(timezone.utc),
        }
        try:
            await asyncio.wait_for(self.queue.put(item), timeout=0.5)
        except (asyncio.QueueFull, asyncio.TimeoutError):
            logger.warning(
                "Trace queue full, falling back to sync write for trace_start"
            )
            asyncio.create_task(self._write_sync(item))

    async def record_trace_end(self, trace_id: str, end_time: datetime):
        """记录 Trace 结束 (自动由 trace_context 调用)"""
        item = {
            "type": "trace_end",
            "trace_id": trace_id,
            "end_time": end_time,
            "timestamp": datetime.now(timezone.utc),
        }
        try:
            await asyncio.wait_for(self.queue.put(item), timeout=0.5)
        except (asyncio.QueueFull, asyncio.TimeoutError):
            logger.warning("Trace queue full, falling back to sync write for trace_end")
            asyncio.create_task(self._write_sync(item))

    async def record_span(
        self,
        trace_id: str,
        span_id: str,
        parent_span_id: str | None,
        name: str,
        duration_ms: int,
        is_error: bool = False,
    ):
        """记录 Span 到队列"""
        if not self._should_sample(is_error):
            return

        item = {
            "type": "span",
            "trace_id": trace_id,
            "span_id": span_id,
            "parent_span_id": parent_span_id,
            "name": name,
            "duration_ms": duration_ms,
            "timestamp": datetime.now(timezone.utc),
        }
        try:
            await asyncio.wait_for(self.queue.put(item), timeout=0.5)
        except (asyncio.QueueFull, asyncio.TimeoutError):
            logger.warning("Trace queue full, falling back to sync write for span")
            asyncio.create_task(self._write_sync(item))

    async def record_llm_start(
        self,
        trace_id: str,
        span_id: str,
        parent_span_id: str | None,
        prompt_messages: list,
        call_parameters: dict,
        request_id: str | None = None,
    ):
        """记录 LLM 调用开始"""
        if not self._should_sample(is_error=False):
            return

        item = {
            "type": "llm_start",
            "trace_id": trace_id,
            "span_id": span_id,
            "parent_span_id": parent_span_id,
            "prompt_messages": prompt_messages,
            "call_parameters": call_parameters,
            "request_id": request_id,
            "timestamp": datetime.now(timezone.utc),
        }
        try:
            await asyncio.wait_for(self.queue.put(item), timeout=0.5)
        except (asyncio.QueueFull, asyncio.TimeoutError):
            logger.warning("Trace queue full, falling back to sync write for llm_start")
            asyncio.create_task(self._write_sync(item))

    async def record_llm_complete(
        self,
        trace_id: str,
        span_id: str,
        parent_span_id: str | None,
        completion_message: str,
        tokens: dict,
        ttft: int,
        request_id: str | None = None,
    ):
        """记录 LLM 调用完成"""
        if not self._should_sample(is_error=False):
            return

        item = {
            "type": "llm_complete",
            "trace_id": trace_id,
            "span_id": span_id,
            "parent_span_id": parent_span_id,
            "completion_message": completion_message,
            "tokens": tokens,
            "ttft": ttft,
            "request_id": request_id,
            "timestamp": datetime.now(timezone.utc),
        }
        try:
            await asyncio.wait_for(self.queue.put(item), timeout=0.5)
        except (asyncio.QueueFull, asyncio.TimeoutError):
            logger.warning(
                "Trace queue full, falling back to sync write for llm_complete"
            )
            asyncio.create_task(self._write_sync(item))

    async def record_llm_error(self, trace_id: str, span_id: str, error: str):
        """记录 LLM 调用错误 (错误全量保留)"""
        if not self._should_sample(is_error=True):
            return

        item = {
            "type": "llm_error",
            "trace_id": trace_id,
            "span_id": span_id,
            "error": error,
            "timestamp": datetime.now(timezone.utc),
        }
        try:
            await asyncio.wait_for(self.queue.put(item), timeout=0.5)
        except (asyncio.QueueFull, asyncio.TimeoutError):
            logger.warning("Trace queue full, falling back to sync write for llm_error")
            asyncio.create_task(self._write_sync(item))

    async def update_trace(
        self,
        trace_id: str,
        status: str,
        total_tokens: int = 0,
        total_cost: Decimal | None = None,
    ):
        """更新 Trace 状态"""
        item = {
            "type": "trace_update",
            "trace_id": trace_id,
            "status": status,
            "total_tokens": total_tokens,
            "total_cost": total_cost,
            "timestamp": datetime.now(timezone.utc),
        }
        try:
            await asyncio.wait_for(self.queue.put(item), timeout=0.5)
        except (asyncio.QueueFull, asyncio.TimeoutError):
            logger.warning(
                "Trace queue full, falling back to sync write for trace_update"
            )
            asyncio.create_task(self._write_sync(item))

    async def _consumer(self):
        """后台消费者，批量写入数据库"""
        batch = []
        last_flush = time.time()

        while self._running:
            try:
                item = await asyncio.wait_for(self.queue.get(), timeout=0.1)
                batch.append(item)
            except asyncio.TimeoutError:
                pass

            if len(batch) >= self.batch_size or (
                batch and time.time() - last_flush >= self.flush_interval
            ):
                await self._flush_batch(batch)
                batch = []
                last_flush = time.time()

    async def _flush_batch(self, batch: list[dict]):
        """批量写入数据库"""
        if not batch:
            return

        try:
            async with async_session_factory() as session:
                async with session.begin():
                    merged_spans: dict[str, dict] = {}
                    for item in batch:
                        if item["type"] in ("llm_start", "llm_complete", "llm_error"):
                            span_id = item.get("span_id")
                            if span_id:
                                if span_id not in merged_spans:
                                    merged_spans[span_id] = {}
                                merged_spans[span_id].update(item)

                    for span_id, merged_item in merged_spans.items():
                        await self._write_llm_call(session, merged_item)

                    for item in batch:
                        if item["type"] == "trace_start":
                            await self._create_trace(session, item)
                        elif item["type"] == "trace_end":
                            await self._finalize_trace(session, item)
                        elif item["type"] == "span":
                            await self._write_span(session, item)
                        elif item["type"] == "trace_update":
                            await self._update_trace(session, item)
        except Exception as e:
            logger.error(f"Failed to flush trace batch: {e}")

    async def _create_trace(self, session, item: dict):
        """创建 Trace 记录"""
        from sqlalchemy import select

        existing = await session.execute(
            select(Trace).where(Trace.trace_id == item["trace_id"])
        )
        if existing.scalar_one_or_none():
            return

        trace = Trace(
            trace_id=item["trace_id"],
            name=item["name"],
            trace_metadata=item.get("metadata"),
            start_time=item["start_time"],
            status=TraceStatus.SUCCESS,
        )
        session.add(trace)

    async def _finalize_trace(self, session, item: dict):
        """更新 Trace 结束时间"""
        from sqlalchemy import select

        result = await session.execute(
            select(Trace).where(Trace.trace_id == item["trace_id"])
        )
        trace = result.scalar_one_or_none()
        if trace:
            trace.end_time = item["end_time"]
            if trace.start_time:
                start = trace.start_time
                if start.tzinfo is None:
                    start = start.replace(tzinfo=timezone.utc)
                trace.total_duration_ms = int(
                    (item["end_time"] - start).total_seconds() * 1000
                )

    async def _write_span(self, session, item: dict):
        """写入 Span 记录 (节点级)"""
        from sqlalchemy import select

        result = await session.execute(
            select(LLMCallLog).where(LLMCallLog.span_id == item["span_id"])
        )
        if result.scalar_one_or_none():
            return

        span = LLMCallLog(
            trace_id=item["trace_id"],
            span_id=item["span_id"],
            parent_span_id=item.get("parent_span_id"),
            call_parameters={"scene": item["name"], "duration_ms": item["duration_ms"]},
            completion_start_time_ms=item["duration_ms"],
            level=CallLevel.INFO,
        )
        session.add(span)

    async def _write_llm_call(self, session, item: dict):
        """写入/更新 LLM 调用记录"""
        from sqlalchemy import select

        span_id = item.get("span_id")
        if not span_id:
            return

        result = await session.execute(
            select(LLMCallLog).where(LLMCallLog.span_id == span_id)
        )
        log = result.scalar_one_or_none()

        if not log:
            from src.models.monitor import LLMCallStatus

            log = LLMCallLog(
                request_id=item.get("request_id") or str(uuid.uuid4()),
                trace_id=item.get("trace_id"),
                span_id=span_id,
                parent_span_id=item.get("parent_span_id"),
                prompt_messages=item.get("prompt_messages"),
                level=CallLevel.INFO,
                model_name=item.get("model_name") or item.get("call_parameters", {}).get("model", "unknown"),
                status=LLMCallStatus.SUCCESS,
            )
            session.add(log)
        elif not log.parent_span_id and item.get("parent_span_id"):
            log.parent_span_id = item["parent_span_id"]

        if "prompt_messages" in item:
            log.prompt_messages = item["prompt_messages"]
        if "completion_message" in item:
            log.completion_message = item["completion_message"]
        if "call_parameters" in item:
            log.call_parameters = item.get("call_parameters", {})
        if "model_parameters" in item:
            log.model_parameters = item["model_parameters"]
        if "tokens" in item:
            tokens = item["tokens"]
            if isinstance(tokens, dict):
                total_tokens = tokens.get(
                    "total_tokens",
                    tokens.get("input_tokens", 0) + tokens.get("output_tokens", 0),
                )
                log.tokens = total_tokens
                model = item.get("call_parameters", {}).get("model", "unknown")
                input_tokens = tokens.get("input_tokens", 0)
                output_tokens = tokens.get("output_tokens", 0)
                log.cost = calculate_cost(model, input_tokens, output_tokens)
            else:
                log.tokens = tokens
        if "ttft" in item:
            log.completion_start_time_ms = item["ttft"]
        if "error" in item:
            log.level = CallLevel.ERROR
            if log.call_parameters:
                log.call_parameters["error"] = item["error"]
            else:
                log.call_parameters = {"error": item["error"]}

    async def _update_trace(self, session, item: dict):
        """更新 Trace 状态"""
        from sqlalchemy import select

        result = await session.execute(
            select(Trace).where(Trace.trace_id == item["trace_id"])
        )
        trace = result.scalar_one_or_none()
        if trace:
            trace.status = TraceStatus(item["status"])
            trace.total_tokens = item.get("total_tokens", 0)
            if item.get("total_cost"):
                trace.total_cost = item["total_cost"]
            trace.end_time = item.get("timestamp")

    async def _write_sync(self, item: dict):
        """同步写入 (队列满时的降级处理)"""
        try:
            async with async_session_factory() as session:
                async with session.begin():
                    if item["type"] == "trace_start":
                        await self._create_trace(session, item)
                    elif item["type"] == "trace_end":
                        await self._finalize_trace(session, item)
                    elif item["type"] == "span":
                        await self._write_span(session, item)
                    elif item["type"] == "trace_update":
                        await self._update_trace(session, item)
                    elif item["type"] in ("llm_start", "llm_complete", "llm_error"):
                        await self._write_llm_call(session, item)
        except Exception as e:
            logger.error(f"Sync trace write failed: {e}")
