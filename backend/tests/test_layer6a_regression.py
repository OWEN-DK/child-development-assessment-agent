import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime
from src.core.validation.layers.layer6a_regression import Layer6aRegressionDetection


@pytest.mark.asyncio
async def test_no_previous_run():
    """无上一次运行时跳过"""
    test_run = MagicMock(id="run-2", test_set_id="ts-1")
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(
        return_value=MagicMock(
            scalars=MagicMock(
                return_value=MagicMock(first=MagicMock(return_value=None))
            )
        )
    )

    session_factory = MagicMock()
    session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    session_factory.return_value.__aexit__ = AsyncMock(return_value=None)

    layer = Layer6aRegressionDetection(session_factory, test_run)
    result = await layer.execute()
    assert result["status"] == "skipped"


@pytest.mark.asyncio
async def test_metric_regression_warning():
    """指标退化 5% 时警告"""
    test_run = MagicMock(id="run-2", test_set_id="ts-1")
    test_run.overall_precision = 0.65
    test_run.overall_recall = 0.80
    test_run.overall_f1 = 0.70
    test_run.overall_mrr = 0.60

    prev_run = MagicMock(id="run-1")
    prev_run.overall_precision = 0.70
    prev_run.overall_recall = 0.80
    prev_run.overall_f1 = 0.75
    prev_run.overall_mrr = 0.65

    session_factory = MagicMock()
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(
        return_value=MagicMock(
            scalars=MagicMock(
                return_value=MagicMock(first=MagicMock(return_value=prev_run))
            )
        )
    )
    session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    session_factory.return_value.__aexit__ = AsyncMock(return_value=None)

    layer = Layer6aRegressionDetection(session_factory, test_run)
    result = await layer.execute()

    assert result["status"] == "completed"
    assert len(result["data"]["regressed_metrics"]) > 0


@pytest.mark.asyncio
async def test_metric_regression_critical():
    """指标退化 15% 时严重警告"""
    test_run = MagicMock(id="run-2", test_set_id="ts-1")
    test_run.overall_precision = 0.50
    test_run.overall_recall = 0.80
    test_run.overall_f1 = 0.55
    test_run.overall_mrr = 0.50

    prev_run = MagicMock(id="run-1")
    prev_run.overall_precision = 0.70
    prev_run.overall_recall = 0.80
    prev_run.overall_f1 = 0.75
    prev_run.overall_mrr = 0.65

    session_factory = MagicMock()
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(
        return_value=MagicMock(
            scalars=MagicMock(
                return_value=MagicMock(first=MagicMock(return_value=prev_run))
            )
        )
    )
    session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    session_factory.return_value.__aexit__ = AsyncMock(return_value=None)

    layer = Layer6aRegressionDetection(session_factory, test_run)
    result = await layer.execute()

    critical_metrics = [
        m for m in result["data"]["regressed_metrics"] if m["severity"] == "critical"
    ]
    assert len(critical_metrics) > 0


@pytest.mark.asyncio
async def test_no_regression_within_threshold():
    """指标退化在阈值内时无警告"""
    test_run = MagicMock(id="run-2", test_set_id="ts-1")
    test_run.overall_precision = 0.68
    test_run.overall_recall = 0.79
    test_run.overall_f1 = 0.73
    test_run.overall_mrr = 0.63

    prev_run = MagicMock(id="run-1")
    prev_run.overall_precision = 0.70
    prev_run.overall_recall = 0.80
    prev_run.overall_f1 = 0.75
    prev_run.overall_mrr = 0.65

    session_factory = MagicMock()
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(
        return_value=MagicMock(
            scalars=MagicMock(
                return_value=MagicMock(first=MagicMock(return_value=prev_run))
            )
        )
    )
    session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    session_factory.return_value.__aexit__ = AsyncMock(return_value=None)

    layer = Layer6aRegressionDetection(session_factory, test_run)
    result = await layer.execute()

    assert result["status"] == "completed"
    assert len(result["data"]["regressed_metrics"]) == 0
    assert len(result["data"]["warnings"]) == 0


@pytest.mark.asyncio
async def test_previous_run_id_included():
    """返回结果包含上一次运行 ID"""
    test_run = MagicMock(id="run-2", test_set_id="ts-1")
    test_run.overall_precision = 0.50
    test_run.overall_recall = 0.50
    test_run.overall_f1 = 0.50
    test_run.overall_mrr = 0.50

    prev_run = MagicMock(id="run-1")
    prev_run.overall_precision = 0.70
    prev_run.overall_recall = 0.80
    prev_run.overall_f1 = 0.75
    prev_run.overall_mrr = 0.65

    session_factory = MagicMock()
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(
        return_value=MagicMock(
            scalars=MagicMock(
                return_value=MagicMock(first=MagicMock(return_value=prev_run))
            )
        )
    )
    session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    session_factory.return_value.__aexit__ = AsyncMock(return_value=None)

    layer = Layer6aRegressionDetection(session_factory, test_run)
    result = await layer.execute()

    assert result["data"]["previous_run_id"] == "run-1"
