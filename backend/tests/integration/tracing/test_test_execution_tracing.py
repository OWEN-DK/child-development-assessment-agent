"""测试执行追踪集成测试"""

import asyncio

import pytest

from src.core.tracing.context import (
    create_span,
    get_current_trace_id,
    trace_context,
)
from src.schemas.monitoring import TraceMetadata
from src.core.tracing.writer import reset_trace_writer


@pytest.mark.asyncio
async def test_test_run_tracing():
    """验证测试运行场景的 Trace 创建"""
    metadata = TraceMetadata(
        test_run_id="tr-001",
        test_set_id="ts-001",
        test_case_id="tc-001",
        model="qwen-plus",
        provider="dashscope",
    )

    async with trace_context("test_run_execution", metadata.model_dump()) as tid:
        assert get_current_trace_id() == tid

        with create_span("test_case_execution") as span_id:
            assert span_id is not None


@pytest.mark.asyncio
async def test_multiple_test_cases_tracing():
    """验证多个测试用例的独立 Trace"""
    trace_ids = []

    for i in range(3):
        metadata = TraceMetadata(
            test_run_id="tr-002",
            test_case_id=f"tc-{i:03d}",
        )
        async with trace_context(f"test_case_{i}", metadata.model_dump()) as tid:
            trace_ids.append(tid)
            await asyncio.sleep(0.01)

    assert len(set(trace_ids)) == 3


@pytest.mark.asyncio
async def test_test_run_with_nested_spans():
    """验证测试运行中嵌套 Span 的层级"""
    async with trace_context("test_run_nested") as tid:
        with create_span("setup") as setup_id:
            pass

        with create_span("execution") as exec_id:
            with create_span("llm_call") as llm_id:
                pass
            with create_span("scoring") as scoring_id:
                pass

        with create_span("teardown") as teardown_id:
            pass

    assert setup_id != exec_id != teardown_id
