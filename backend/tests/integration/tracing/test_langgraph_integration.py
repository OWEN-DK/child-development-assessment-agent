"""LangGraph 追踪集成测试"""

import asyncio

import pytest

from src.core.tracing.context import (
    create_span,
    get_current_span_id,
    get_current_trace_id,
    trace_context,
)
from src.core.tracing.writer import reset_trace_writer


@pytest.mark.asyncio
async def test_trace_context_with_asyncio_gather():
    """验证多个并发 Trace 上下文互不干扰"""
    results = []

    async def run_node(trace_name, node_name):
        async with trace_context(trace_name) as tid:
            with create_span(node_name) as span_id:
                await asyncio.sleep(0.01)
                results.append(
                    {
                        "trace_name": trace_name,
                        "trace_id": get_current_trace_id(),
                        "span_id": get_current_span_id(),
                        "node_name": node_name,
                    }
                )

    await asyncio.gather(
        run_node("trace_a", "node_preprocessing"),
        run_node("trace_b", "node_validation"),
        run_node("trace_c", "node_assessment"),
    )

    trace_ids = [r["trace_id"] for r in results]
    assert len(set(trace_ids)) == 3, "每个 Trace 应有独立的 trace_id"


@pytest.mark.asyncio
async def test_nested_spans_in_trace():
    """验证 Trace 内嵌套多个 Span 的层级关系"""
    span_ids = []

    async with trace_context("nested_test") as tid:
        with create_span("parent") as parent_id:
            span_ids.append(("parent", parent_id, None))
            with create_span("child_1") as child1_id:
                span_ids.append(("child_1", child1_id, parent_id))
            with create_span("child_2") as child2_id:
                span_ids.append(("child_2", child2_id, parent_id))
                with create_span("grandchild") as gc_id:
                    span_ids.append(("grandchild", gc_id, child2_id))

    assert len(span_ids) == 4
    assert span_ids[0][2] is None
    assert span_ids[1][2] == span_ids[0][1]
    assert span_ids[2][2] == span_ids[0][1]
    assert span_ids[3][2] == span_ids[2][1]


@pytest.mark.asyncio
async def test_trace_context_cleanup():
    """验证 Trace 上下文退出后正确清理"""
    async with trace_context("cleanup_test") as tid:
        pass

    assert get_current_trace_id() is None
    assert get_current_span_id() is None


@pytest.mark.asyncio
async def test_span_context_cleanup():
    """验证 Span 上下文退出后正确清理"""
    async with trace_context("span_cleanup_test") as tid:
        with create_span("temp_span") as span_id:
            assert get_current_span_id() == span_id
        assert get_current_span_id() is None

    assert get_current_trace_id() is None
