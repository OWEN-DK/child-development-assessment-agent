"""LLM 调用追踪模块

采用 contextvars 实现 task-local 的 Trace/Span 上下文传递，
LangGraph 节点自动埋点创建 Span，异步队列写入 MySQL 存储。
"""

from src.core.tracing.context import (
    trace_context,
    create_span,
    get_current_trace_id,
    get_current_span_id,
    get_parent_span_id,
)
from src.core.tracing.writer import get_trace_writer, reset_trace_writer
from src.core.tracing.schemas import TraceMetadata

__all__ = [
    "trace_context",
    "create_span",
    "get_current_trace_id",
    "get_current_span_id",
    "get_parent_span_id",
    "get_trace_writer",
    "reset_trace_writer",
    "TraceMetadata",
]
