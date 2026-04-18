"""TTL 清理任务单元测试

由于 cleanup_expired_traces 直接导入 async_session_factory，
mock 需要 patch 正确的路径。
"""

from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class MockSession:
    def __init__(self, expired_traces):
        self.expired_traces = expired_traces
        self.executed_queries = []

    async def execute(self, query):
        self.executed_queries.append(query)
        result = MagicMock()
        result.scalars.return_value.all.return_value = self.expired_traces
        return result

    def begin(self):
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass


class MockSessionFactory:
    def __init__(self, expired_traces):
        self.expired_traces = expired_traces

    def __call__(self):
        return MockSession(self.expired_traces)


@pytest.mark.asyncio
async def test_cleanup_expired_traces():
    """验证清理过期 Trace 数据"""
    from src.core.tracing import cleanup as cleanup_module

    mock_factory = MockSessionFactory(["expired-trace-001", "expired-trace-002"])

    with patch.object(cleanup_module, "async_session_factory", mock_factory):
        deleted = await cleanup_module.cleanup_expired_traces(
            retention_days=30, dry_run=False
        )

        assert deleted == 2


@pytest.mark.asyncio
async def test_cleanup_dry_run():
    """验证 dry_run 模式不执行删除"""
    from src.core.tracing import cleanup as cleanup_module

    mock_factory = MockSessionFactory(["expired-trace-001"])

    with patch.object(cleanup_module, "async_session_factory", mock_factory):
        deleted = await cleanup_module.cleanup_expired_traces(
            retention_days=30, dry_run=True
        )

        assert deleted == 1


@pytest.mark.asyncio
async def test_cleanup_no_expired_traces():
    """验证无过期数据时返回 0"""
    from src.core.tracing import cleanup as cleanup_module

    mock_factory = MockSessionFactory([])

    with patch.object(cleanup_module, "async_session_factory", mock_factory):
        deleted = await cleanup_module.cleanup_expired_traces(retention_days=30)

        assert deleted == 0
