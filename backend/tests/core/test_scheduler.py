"""测试定时任务调度器 - 核心逻辑"""

import pytest
from unittest.mock import patch, AsyncMock


@pytest.mark.asyncio
async def test_cleanup_expired_reports():
    """测试过期报告清理函数"""
    from src.core.scheduler import cleanup_expired_reports
    from src.service.rag_report_service import rag_report_service

    with patch.object(
        rag_report_service, "cleanup_expired_reports", new_callable=AsyncMock
    ) as mock_cleanup:
        await cleanup_expired_reports()
        mock_cleanup.assert_called_once_with(retention_days=30)


@pytest.mark.asyncio
async def test_cleanup_orphaned_drafts():
    """测试孤儿草稿清理函数"""
    from src.core.scheduler import cleanup_orphaned_drafts
    from src.core.database import db_session_factory
    from unittest.mock import MagicMock

    # Mock 数据库会话
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_session.execute.return_value = mock_result

    with patch("src.core.scheduler.db_session_factory") as mock_factory:
        mock_factory.return_value.__aenter__.return_value = mock_session
        mock_factory.return_value.__aexit__.return_value = None

        await cleanup_orphaned_drafts()

        # 验证执行了查询
        mock_session.execute.assert_called_once()


def test_scheduler_module_imports():
    """测试调度器模块可以正常导入"""
    from src.core.scheduler import (
        scheduler,
        cleanup_expired_reports,
        cleanup_orphaned_drafts,
    )

    assert scheduler is not None
    assert callable(cleanup_expired_reports)
    assert callable(cleanup_orphaned_drafts)
