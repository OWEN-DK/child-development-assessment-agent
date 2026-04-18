"""LLMCallLog 扩展字段单元测试"""

import pytest


def test_llm_call_log_span_fields():
    from src.models.monitor import LLMCallLog, CallLevel

    log = LLMCallLog(
        trace_id="test-trace-001",
        span_id="span-001",
        parent_span_id=None,
        prompt_messages=[{"role": "system", "content": "test"}],
        completion_message="test response",
        call_parameters={"provider": "dashscope", "temperature": 0.7},
        level=CallLevel.INFO,
    )
    assert log.trace_id == "test-trace-001"
    assert log.span_id == "span-001"
    assert log.parent_span_id is None
    assert log.level == CallLevel.INFO


def test_call_level_enum():
    from src.models.monitor import CallLevel

    assert CallLevel.INFO.value == "INFO"
    assert CallLevel.WARNING.value == "WARNING"
    assert CallLevel.ERROR.value == "ERROR"


def test_llm_call_log_cost_field():
    from src.models.monitor import LLMCallLog, CallLevel
    from decimal import Decimal

    log = LLMCallLog(
        trace_id="test-trace-002",
        span_id="span-002",
        cost=Decimal("0.0123"),
        tokens=1500,
        completion_start_time_ms=200,
        level=CallLevel.INFO,
    )
    assert log.cost == Decimal("0.0123")
    assert log.tokens == 1500
    assert log.completion_start_time_ms == 200


def test_llm_call_log_full_content_paths():
    from src.models.monitor import LLMCallLog, CallLevel

    log = LLMCallLog(
        trace_id="test-trace-003",
        span_id="span-003",
        full_prompt_path="storage/traces/test-trace-003_span-003_prompt.json",
        full_completion_path="storage/traces/test-trace-003_span-003_completion.json",
        level=CallLevel.INFO,
    )
    assert "test-trace-003" in log.full_prompt_path
    assert "span-003" in log.full_completion_path
