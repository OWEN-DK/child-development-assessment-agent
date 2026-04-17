"""Layer 6 手动触发测试"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from src.core.validation.layers.layer6_runner import Layer6Runner


@pytest.mark.asyncio
async def test_trigger_layer6_success():
    """成功触发 Layer 6 校验"""
    test_run = MagicMock(id="run-1", test_set_id="ts-1")
    session_factory = AsyncMock()

    runner = Layer6Runner(session_factory, test_run)

    # Mock all 4 sublayers
    with patch(
        "src.core.validation.layers.layer6_runner.Layer6aRegressionDetection"
    ) as mock_reg:
        with patch(
            "src.core.validation.layers.layer6_runner.Layer6bCrossValidation"
        ) as mock_cv:
            with patch(
                "src.core.validation.layers.layer6_runner.Layer6cCostEffectiveness"
            ) as mock_ce:
                with patch(
                    "src.core.validation.layers.layer6_runner.Layer6dABShadowTest"
                ) as mock_ab:
                    mock_reg.return_value.execute = AsyncMock(
                        return_value={"status": "completed", "data": {}}
                    )
                    mock_cv.return_value.execute = AsyncMock(
                        return_value={"status": "completed", "data": {}}
                    )
                    mock_ce.return_value.execute = AsyncMock(
                        return_value={"status": "completed", "data": {}}
                    )
                    mock_ab.return_value.execute = AsyncMock(
                        return_value={"status": "completed", "data": {}}
                    )

                    result = await runner.execute()

                    assert result["status"] == "completed"
                    assert "regression" in result["data"]
                    assert "cross_validation" in result["data"]
                    assert "cost_effectiveness" in result["data"]
                    assert "ab_shadow_test" in result["data"]


@pytest.mark.asyncio
async def test_layer6_partial_failure():
    """部分子层失败时聚合状态"""
    test_run = MagicMock(id="run-1", test_set_id="ts-1")
    session_factory = AsyncMock()

    runner = Layer6Runner(session_factory, test_run)

    with patch(
        "src.core.validation.layers.layer6_runner.Layer6aRegressionDetection"
    ) as mock_reg:
        with patch(
            "src.core.validation.layers.layer6_runner.Layer6bCrossValidation"
        ) as mock_cv:
            with patch(
                "src.core.validation.layers.layer6_runner.Layer6cCostEffectiveness"
            ) as mock_ce:
                with patch(
                    "src.core.validation.layers.layer6_runner.Layer6dABShadowTest"
                ) as mock_ab:
                    mock_reg.return_value.execute = AsyncMock(
                        return_value={"status": "completed", "data": {}}
                    )
                    mock_cv.return_value.execute = AsyncMock(
                        side_effect=ValueError("DB error")
                    )
                    mock_ce.return_value.execute = AsyncMock(
                        return_value={
                            "status": "skipped",
                            "data": {"reason": "no data"},
                        }
                    )
                    mock_ab.return_value.execute = AsyncMock(
                        return_value={"status": "completed", "data": {}}
                    )

                    result = await runner.execute()

                    assert result["status"] == "degraded"
                    assert result["data"]["cross_validation"]["status"] == "degraded"
