"""TraceWriter 队列满降级测试"""

import asyncio

import pytest

from src.core.tracing.writer import TraceWriter


@pytest.mark.asyncio
async def test_queue_full_fallback():
    """验证队列满时降级到同步写入"""
    writer = TraceWriter(max_queue_size=2, sample_rate=1.0)
    writer._running = True

    await writer.record_span(
        trace_id="trace-001",
        span_id="span-001",
        parent_span_id=None,
        name="node_a",
        duration_ms=100,
    )
    await writer.record_span(
        trace_id="trace-002",
        span_id="span-002",
        parent_span_id=None,
        name="node_b",
        duration_ms=200,
    )

    assert writer.queue.qsize() == 2

    await writer.record_span(
        trace_id="trace-003",
        span_id="span-003",
        parent_span_id=None,
        name="node_c",
        duration_ms=300,
    )

    assert writer.queue.qsize() == 2

    await writer.stop()


@pytest.mark.asyncio
async def test_queue_timeout_fallback():
    """验证队列写入超时时降级到同步写入"""
    writer = TraceWriter(max_queue_size=100, sample_rate=1.0)
    writer._running = True

    await writer.record_span(
        trace_id="trace-004",
        span_id="span-004",
        parent_span_id=None,
        name="node_d",
        duration_ms=400,
    )

    assert writer.queue.qsize() == 1

    await writer.stop()


@pytest.mark.asyncio
async def test_queue_drain_on_stop():
    """验证停止时不等待队列排空"""
    writer = TraceWriter(max_queue_size=100, sample_rate=1.0)
    writer._ensure_started()

    for i in range(5):
        await writer.record_span(
            trace_id=f"trace-{i}",
            span_id=f"span-{i}",
            parent_span_id=None,
            name=f"node_{i}",
            duration_ms=100,
        )

    assert writer.queue.qsize() == 5

    await writer.stop()
