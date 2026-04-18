"""LLM 调用追踪单元测试"""

import asyncio

import pytest

from src.core.tracing.context import (
    create_span,
    get_current_span_id,
    get_current_trace_id,
    trace_context,
)
from src.core.tracing.writer import TraceWriter, reset_trace_writer


@pytest.mark.asyncio
async def test_llm_call_tracing_flow():
    """验证 LLM 调用完整追踪流程"""
    writer = TraceWriter(sample_rate=1.0)
    writer._ensure_started()

    async with trace_context("llm_call_test") as tid:
        with create_span("llm_call") as span_id:
            await writer.record_llm_start(
                trace_id=tid,
                span_id=span_id,
                parent_span_id=None,
                prompt_messages=[{"role": "user", "content": "test"}],
                call_parameters={"model": "qwen-plus", "temperature": 0.7},
            )

            await asyncio.sleep(0.01)

            await writer.record_llm_complete(
                trace_id=tid,
                span_id=span_id,
                parent_span_id=None,
                completion_message="test response",
                tokens={"input_tokens": 100, "output_tokens": 50},
                ttft=200,
            )

    assert writer.queue.qsize() >= 1

    await writer.stop()


@pytest.mark.asyncio
async def test_llm_call_error_tracing():
    """验证 LLM 调用错误追踪"""
    writer = TraceWriter(sample_rate=1.0, error_sample_rate=1.0)
    writer._ensure_started()

    async with trace_context("llm_error_test") as tid:
        with create_span("llm_call_error") as span_id:
            await writer.record_llm_error(
                trace_id=tid,
                span_id=span_id,
                error="API timeout after 30s",
            )

    assert writer.queue.qsize() >= 1

    await writer.stop()


@pytest.mark.asyncio
async def test_llm_call_with_parent_span():
    """验证 LLM 调用正确关联父 Span"""
    writer = TraceWriter(sample_rate=1.0)
    writer._ensure_started()

    async with trace_context("llm_parent_test") as tid:
        with create_span("assessment_node") as parent_id:
            with create_span("llm_call_nested") as child_id:
                await writer.record_llm_start(
                    trace_id=tid,
                    span_id=child_id,
                    parent_span_id=parent_id,
                    prompt_messages=[{"role": "user", "content": "nested"}],
                    call_parameters={"model": "qwen-plus"},
                )

    assert writer.queue.qsize() >= 1
    item = writer.queue.get_nowait()
    assert item["parent_span_id"] == parent_id

    await writer.stop()
