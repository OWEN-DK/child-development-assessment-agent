"""TraceWriter 单元测试"""

import pytest

from src.core.tracing.writer import TraceWriter


@pytest.mark.asyncio
async def test_writer_enqueue():
    writer = TraceWriter(max_queue_size=100)
    writer._ensure_started()

    await writer.record_span(
        trace_id="test-trace-001",
        span_id="span-001",
        parent_span_id=None,
        name="test_node",
        duration_ms=100,
    )

    assert writer.queue.qsize() == 1

    await writer.stop()


@pytest.mark.asyncio
async def test_writer_sampling():
    writer = TraceWriter(sample_rate=0.0)

    await writer.record_span(
        trace_id="test-trace-002",
        span_id="span-002",
        parent_span_id=None,
        name="test_node",
        duration_ms=100,
        is_error=False,
    )
    assert writer.queue.qsize() == 0


@pytest.mark.asyncio
async def test_writer_error_sampling():
    writer = TraceWriter(sample_rate=0.0, error_sample_rate=1.0)
    writer._ensure_started()

    await writer.record_span(
        trace_id="test-trace-003",
        span_id="span-003",
        parent_span_id=None,
        name="test_node",
        duration_ms=100,
        is_error=True,
    )
    assert writer.queue.qsize() == 1

    await writer.stop()


@pytest.mark.asyncio
async def test_writer_llm_complete_with_parent_span():
    """验证 record_llm_complete 正确传递 parent_span_id"""
    writer = TraceWriter(sample_rate=1.0)
    writer._ensure_started()

    await writer.record_llm_complete(
        trace_id="test-trace-004",
        span_id="span-004",
        parent_span_id="parent-span-001",
        completion_message="test response",
        tokens={"input_tokens": 100, "output_tokens": 50},
        ttft=200,
    )

    assert writer.queue.qsize() == 1
    item = writer.queue.get_nowait()
    assert item["parent_span_id"] == "parent-span-001"

    await writer.stop()
