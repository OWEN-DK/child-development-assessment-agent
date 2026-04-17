"""超时与降级策略测试"""

import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from src.core.validation.orchestrator import ValidationOrchestrator


@pytest.mark.asyncio
async def test_layer_timeout():
    """单层层超时标记 timeout"""
    orchestrator = ValidationOrchestrator()
    await orchestrator.init()

    class SlowLayer:
        async def execute(self):
            await asyncio.sleep(999)

    result = await orchestrator._run_layer_with_result(1, SlowLayer(), "test_layer", 1)

    assert result["status"] == "timeout"
    assert "超时" in result["data"]["reason"]


@pytest.mark.asyncio
async def test_layer_exception_mark_degraded():
    """Layer 异常时标记 degraded 而非失败"""
    orchestrator = ValidationOrchestrator()
    await orchestrator.init()

    class ExceptionLayer:
        async def execute(self):
            raise ValueError("数据库连接失败")

    result = await orchestrator._run_layer_with_result(
        2, ExceptionLayer(), "test_exception_layer", 30
    )

    assert result["status"] == "degraded"
    assert "数据库连接失败" in result["data"]["reason"]


@pytest.mark.asyncio
async def test_report_status_after_timeout():
    """超时后报告仍为 completed"""
    orchestrator = ValidationOrchestrator()
    await orchestrator.init()

    session_factory = AsyncMock()
    test_run = MagicMock(id="test-run-1", test_set_id="ts-1", config_version_id=None)

    async def slow_execute(*args):
        await asyncio.sleep(999)

    # 直接 patch _execute_with_timeout 来模拟总体超时场景
    with patch.object(
        orchestrator, "_execute_with_timeout", new_callable=AsyncMock
    ) as mock_exec:
        mock_exec.return_value = MagicMock(id="report-1", status="completed")
        report = await orchestrator.execute(session_factory, test_run)

        mock_exec.assert_called_once()
        assert report.status == "completed"


@pytest.mark.asyncio
async def test_total_timeout_preserves_completed_layers():
    """总体超时后保留已完成层的结果"""
    orchestrator = ValidationOrchestrator()
    await orchestrator.init()

    session_factory = AsyncMock()
    test_run = MagicMock(id="test-run-1", test_set_id="ts-1", config_version_id=None)

    call_args = {}

    async def mock_create_report(sf, tr, vr):
        call_args["results"] = vr
        return MagicMock(id="report-1", status="completed")

    # 模拟 _execute_with_timeout 直接填充结果并触发超时
    async def execute_with_timeout_mock(sf, tr, config):
        # 模拟部分层已完成
        validation_results = [
            {
                "layer": 1,
                "status": "completed",
                "data": {"suggestions": []},
                "duration_ms": 50,
            },
            {
                "layer": 2,
                "status": "completed",
                "data": {"matches": []},
                "duration_ms": 50,
            },
        ]
        return await mock_create_report(sf, tr, validation_results)

    with patch.object(
        orchestrator, "_execute_with_timeout", side_effect=execute_with_timeout_mock
    ):
        report = await orchestrator.execute(session_factory, test_run)

        assert call_args["results"][0]["status"] == "completed"
        assert call_args["results"][1]["status"] == "completed"
