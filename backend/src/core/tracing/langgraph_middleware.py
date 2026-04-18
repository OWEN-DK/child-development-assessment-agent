"""LangGraph 追踪中间件

为 LangGraph 节点自动创建 Span，记录执行时间。
"""

import asyncio
import time
from contextlib import contextmanager
from typing import Generator

from src.core.tracing.context import (
    create_span,
    get_current_span_id,
    get_current_trace_id,
    get_parent_span_id,
    _get_span_stack,
)
from src.core.tracing.writer import get_trace_writer


class TracingMiddleware:
    """LangGraph 节点追踪中间件"""

    def __init__(self):
        self.writer = get_trace_writer()

    @contextmanager
    def trace_node(self, node_name: str) -> Generator[str, None, None]:
        """为 LangGraph 节点创建 Span"""
        span_id = None
        start_time = time.time()

        with create_span(node_name) as span_id:
            try:
                yield span_id
            finally:
                duration_ms = int((time.time() - start_time) * 1000)
                # 使用 asyncio.create_task 避免阻塞主流程
                asyncio.create_task(
                    self.writer.record_span(
                        trace_id=get_current_trace_id(),
                        span_id=span_id,
                        parent_span_id=get_parent_span_id(),
                        name=node_name,
                        duration_ms=duration_ms,
                    )
                )
