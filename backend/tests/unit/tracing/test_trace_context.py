"""TraceContext 单元测试"""

import asyncio

import pytest

from src.core.tracing.context import (
    create_span,
    get_current_span_id,
    get_current_trace_id,
    get_parent_span_id,
    trace_context,
    trace_id,
    span_stack,
)


@pytest.mark.asyncio
async def test_trace_context_creation():
    async with trace_context("test_trace", {"key": "value"}) as tid:
        assert tid is not None
        assert get_current_trace_id() == tid


@pytest.mark.asyncio
async def test_span_hierarchy():
    async with trace_context("test_trace") as tid:
        with create_span("parent_span") as parent_id:
            assert get_current_span_id() == parent_id
            assert get_parent_span_id() is None
            with create_span("child_span") as child_id:
                assert get_current_span_id() == child_id
                assert get_parent_span_id() == parent_id
            assert get_current_span_id() == parent_id
            assert get_parent_span_id() is None


@pytest.mark.asyncio
async def test_concurrent_isolation():
    results = []

    async def run_trace(name):
        async with trace_context(name) as tid:
            await asyncio.sleep(0.01)
            results.append((name, get_current_trace_id()))

    await asyncio.gather(run_trace("trace_a"), run_trace("trace_b"))

    assert results[0][1] != results[1][1]


@pytest.mark.asyncio
async def test_concurrent_span_isolation():
    """验证并发场景下 Span 栈不互相污染"""

    async def run_with_spans(name, results):
        async with trace_context(name) as tid:
            with create_span(f"{name}_parent") as parent_id:
                await asyncio.sleep(0.01)
                with create_span(f"{name}_child") as child_id:
                    await asyncio.sleep(0.01)
                    assert get_current_span_id() == child_id
                assert get_current_span_id() == parent_id
                results.append((name, tid, parent_id))

    results_a = []
    results_b = []
    await asyncio.gather(
        run_with_spans("trace_a", results_a),
        run_with_spans("trace_b", results_b),
    )

    assert results_a[0][1] != results_b[0][1]
    assert results_a[0][2] != results_b[0][2]


def test_context_vars_reset():
    """验证 contextvars 在退出上下文后正确重置"""
    trace_id.set(None)
    span_stack.set([])

    assert get_current_trace_id() is None
    assert get_current_span_id() is None
    assert get_parent_span_id() is None
