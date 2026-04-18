"""追踪 API 集成测试"""

from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.service.trace_service import TraceService
from src.models.trace import Trace, TraceStatus
from src.models.monitor import LLMCallLog, CallLevel


@pytest.mark.asyncio
async def test_list_traces():
    """验证分页查询 Trace 列表"""
    service = TraceService()

    mock_trace1 = Trace(
        trace_id="trace-001",
        name="test_run",
        status=TraceStatus.SUCCESS,
        total_tokens=1000,
        total_duration_ms=500,
        total_cost=Decimal("0.01"),
        created_at=datetime.utcnow(),
    )
    mock_trace2 = Trace(
        trace_id="trace-002",
        name="assessment",
        status=TraceStatus.SUCCESS,
        total_tokens=2000,
        total_duration_ms=800,
        total_cost=Decimal("0.02"),
        created_at=datetime.utcnow(),
    )

    mock_session = MagicMock()
    mock_count_result = MagicMock()
    mock_count_result.scalar.return_value = 2
    mock_items_result = MagicMock()
    mock_items_result.scalars.return_value.all.return_value = [mock_trace1, mock_trace2]

    call_count = [0]

    async def mock_execute(query):
        call_count[0] += 1
        if call_count[0] == 1:
            return mock_count_result
        return mock_items_result

    mock_session.execute = mock_execute

    items, total = await service.list_traces(mock_session, page=1, page_size=10)

    assert total == 2
    assert len(items) == 2
    assert items[0].trace_id == "trace-001"


@pytest.mark.asyncio
async def test_get_trace_detail():
    """验证获取 Trace 详情"""
    service = TraceService()

    mock_trace = Trace(
        trace_id="trace-001",
        name="test_run",
        status=TraceStatus.SUCCESS,
        total_tokens=1000,
        total_duration_ms=500,
        total_cost=Decimal("0.01"),
        start_time=datetime.utcnow(),
        created_at=datetime.utcnow(),
    )

    mock_session = MagicMock()
    mock_trace_result = MagicMock()
    mock_trace_result.scalar_one_or_none.return_value = mock_trace
    mock_spans_result = MagicMock()
    mock_spans_result.scalars.return_value.all.return_value = []

    call_count = [0]

    async def mock_execute(query):
        call_count[0] += 1
        if call_count[0] == 1:
            return mock_trace_result
        return mock_spans_result

    mock_session.execute = mock_execute

    result = await service.get_trace_detail(mock_session, "trace-001")

    assert result is not None
    assert result["trace_id"] == "trace-001"
    assert result["status"] == "success"


@pytest.mark.asyncio
async def test_get_trace_detail_not_found():
    """验证 Trace 不存在时返回 None"""
    service = TraceService()

    mock_session = MagicMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute = AsyncMock(return_value=mock_result)

    result = await service.get_trace_detail(mock_session, "nonexistent")

    assert result is None


@pytest.mark.asyncio
async def test_list_llm_call_logs():
    """验证分页查询 LLM 调用日志"""
    service = TraceService()

    mock_log = LLMCallLog(
        id=1,
        trace_id="trace-001",
        span_id="span-001",
        model_name="qwen-plus",
        tokens=1500,
        level=CallLevel.INFO,
        created_at=datetime.utcnow(),
    )

    mock_session = MagicMock()
    mock_count_result = MagicMock()
    mock_count_result.scalar.return_value = 1
    mock_items_result = MagicMock()
    mock_items_result.scalars.return_value.all.return_value = [mock_log]

    call_count = [0]

    async def mock_execute(query):
        call_count[0] += 1
        if call_count[0] == 1:
            return mock_count_result
        return mock_items_result

    mock_session.execute = mock_execute

    items, total = await service.list_llm_call_logs(mock_session, page=1, page_size=10)

    assert total == 1
    assert len(items) == 1
    assert items[0].model_name == "qwen-plus"


@pytest.mark.asyncio
async def test_get_cost_analysis():
    """验证成本分析"""
    service = TraceService()

    mock_log1 = LLMCallLog(
        id=1,
        model_name="qwen-plus",
        tokens=1000,
        cost=Decimal("0.01"),
        call_parameters={"model": "qwen-plus"},
        created_at=datetime.utcnow(),
    )
    mock_log2 = LLMCallLog(
        id=2,
        model_name="qwen-plus",
        tokens=500,
        cost=Decimal("0.005"),
        call_parameters={"model": "qwen-plus"},
        created_at=datetime.utcnow(),
    )

    mock_session = MagicMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [mock_log1, mock_log2]
    mock_session.execute = AsyncMock(return_value=mock_result)

    result = await service.get_cost_analysis(mock_session)

    assert result["total_calls"] == 2
    assert result["total_tokens"] == 1500


@pytest.mark.asyncio
async def test_get_latency_distribution():
    """验证延迟分布计算"""
    service = TraceService()

    mock_session = MagicMock()
    mock_result = MagicMock()
    mock_result.all.return_value = [(100,), (200,), (300,), (400,), (500,)]
    mock_session.execute = AsyncMock(return_value=mock_result)

    result = await service.get_latency_distribution(mock_session)

    assert result["p50"] == 300
    assert result["p95"] == 500
    assert result["min"] == 100
    assert result["max"] == 500


@pytest.mark.asyncio
async def test_get_error_analysis():
    """验证错误分析"""
    service = TraceService()

    mock_error1 = LLMCallLog(
        id=1,
        trace_id="trace-001",
        span_id="span-001",
        level=CallLevel.ERROR,
        call_parameters={"error": "TimeoutError: API timeout"},
        created_at=datetime.utcnow(),
    )
    mock_error2 = LLMCallLog(
        id=2,
        trace_id="trace-002",
        span_id="span-002",
        level=CallLevel.ERROR,
        call_parameters={"error": "TimeoutError: Connection refused"},
        created_at=datetime.utcnow(),
    )

    mock_session = MagicMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [mock_error1, mock_error2]
    mock_session.execute = AsyncMock(return_value=mock_result)

    result = await service.get_error_analysis(mock_session)

    assert result["total_errors"] == 2
    assert len(result["error_types"]) == 1
    assert result["error_types"][0]["type"] == "TimeoutError"
    assert result["error_types"][0]["count"] == 2
