"""Trace 模型单元测试"""

from datetime import datetime
from decimal import Decimal

import pytest


def test_trace_model_creation():
    from src.models.trace import Trace, TraceStatus

    trace = Trace(
        trace_id="test-trace-001",
        name="assessment_run",
        user_id="user-123",
        trace_metadata={"child_profile_id": "cp-456"},
        status=TraceStatus.SUCCESS,
        start_time=datetime.utcnow(),
    )
    assert trace.trace_id == "test-trace-001"
    assert trace.status == TraceStatus.SUCCESS
    assert trace.trace_metadata == {"child_profile_id": "cp-456"}


def test_trace_status_enum():
    from src.models.trace import TraceStatus

    assert TraceStatus.SUCCESS.value == "success"
    assert TraceStatus.FAILED.value == "failed"
    assert TraceStatus.PARTIAL.value == "partial"


def test_trace_metadata_serialization():
    from src.models.trace import Trace, TraceStatus
    from src.core.tracing.schemas import TraceMetadata

    metadata = TraceMetadata(
        child_profile_id="cp-456",
        test_run_id="tr-789",
        model="qwen-plus",
    )
    metadata_dict = metadata.model_dump()

    trace = Trace(
        trace_id="test-trace-002",
        name="test_run",
        trace_metadata=metadata_dict,
        status=TraceStatus.SUCCESS,
        start_time=datetime.utcnow(),
    )
    assert trace.trace_metadata["child_profile_id"] == "cp-456"
    assert trace.trace_metadata["model"] == "qwen-plus"
