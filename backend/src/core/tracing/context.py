"""TraceContext - 使用 contextvars 实现 task-local 的 Trace/Span 上下文传递"""

import uuid
from contextlib import asynccontextmanager, contextmanager
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Generator

trace_id: ContextVar[str | None] = ContextVar("trace_id", default=None)
span_stack: ContextVar[list[str]] = ContextVar("span_stack", default=None)


def _get_span_stack() -> list[str]:
    """安全获取 span_stack，避免跨 task 共享引用"""
    stack = span_stack.get()
    if stack is None:
        stack = []
        span_stack.set(stack)
    return stack


def get_current_trace_id() -> str | None:
    return trace_id.get()


def get_current_span_id() -> str | None:
    stack = _get_span_stack()
    return stack[-1] if stack else None


def get_parent_span_id() -> str | None:
    """获取父 Span ID (栈中倒数第二个元素)"""
    stack = _get_span_stack()
    return stack[-2] if len(stack) >= 2 else None


@asynccontextmanager
async def trace_context(name: str, metadata: dict | None = None):
    """创建 Trace 上下文（async 版本）

    自动记录 start_time 和 end_time，并通过 TraceWriter 写入数据库。
    """
    from src.core.tracing.writer import get_trace_writer

    tid = str(uuid.uuid4())
    start_time = datetime.now(UTC)
    trace_token = trace_id.set(tid)
    span_token = span_stack.set([])

    writer = get_trace_writer()
    await writer.record_trace_start(
        trace_id=tid,
        name=name,
        metadata=metadata or {},
        start_time=start_time,
    )

    try:
        yield tid
    finally:
        end_time = datetime.now(UTC)
        await writer.record_trace_end(trace_id=tid, end_time=end_time)
        trace_id.reset(trace_token)
        span_stack.reset(span_token)


@contextmanager
def trace_context_sync(name: str, metadata: dict | None = None):
    """创建 Trace 上下文（sync 版本，仅用于同步场景）

    通过 asyncio.ensure_future 将异步写入操作提交到事件循环，
    避免 coroutine 未被 await 导致 trace start 记录丢失。
    """
    import asyncio

    from src.core.tracing.writer import get_trace_writer

    tid = str(uuid.uuid4())
    start_time = datetime.now(UTC)
    trace_token = trace_id.set(tid)
    span_token = span_stack.set([])

    writer = get_trace_writer()
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(
            writer.record_trace_start(
                trace_id=tid, name=name, metadata=metadata or {}, start_time=start_time
            )
        )
    except RuntimeError:
        # 无运行中的事件循环，跳过异步写入
        pass

    try:
        yield tid
    finally:
        end_time = datetime.now(UTC)
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(
                writer.record_trace_end(trace_id=tid, end_time=end_time)
            )
        except RuntimeError:
            pass
        trace_id.reset(trace_token)
        span_stack.reset(span_token)


@contextmanager
def create_span(name: str) -> Generator[str, None, None]:
    """创建 Span 并维护父子关系栈

    注意：此函数仅维护 span 栈，不直接写入数据库。
    写入由调用方（如 LangGraph 中间件）负责。
    """
    import time

    span_id = str(uuid.uuid4())
    start_time = time.time()
    stack = _get_span_stack().copy()
    stack.append(span_id)
    token = span_stack.set(stack)

    try:
        yield span_id
    finally:
        try:
            span_stack.reset(token)
        except ValueError:
            # 生成器在不同的 asyncio Context 中被清理（如 GC 回收），
            # token 已失效，跳过重置即可
            pass
