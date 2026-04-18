"""采样策略单元测试"""

import pytest

from src.core.tracing.writer import TraceWriter


@pytest.mark.asyncio
async def test_sample_rate_accuracy():
    """验证采样率准确性（允许 ±10% 误差）"""
    writer = TraceWriter(sample_rate=0.1, error_sample_rate=1.0)

    total_calls = 1000
    sampled = 0

    for _ in range(total_calls):
        if writer._should_sample(is_error=False):
            sampled += 1

    expected = total_calls * 0.1
    assert abs(sampled - expected) <= expected * 0.1


@pytest.mark.asyncio
async def test_error_always_sampled():
    """验证错误调用全量保留"""
    writer = TraceWriter(sample_rate=0.0, error_sample_rate=1.0)

    for _ in range(100):
        assert writer._should_sample(is_error=True) is True
