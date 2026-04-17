import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime
from src.core.validation.layers.layer2_history import Layer2HistoryComparison


@pytest.mark.asyncio
async def test_no_history_baseline():
    """无历史运行时返回基准报告"""
    test_run = MagicMock(
        id="run-1",
        test_set_id="ts-1",
        config_version_id=None,
        overall_precision=0.7,
        overall_recall=0.8,
        overall_f1=0.75,
        overall_mrr=0.6,
    )

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_session.execute = AsyncMock(return_value=mock_result)

    # 创建正确的异步上下文管理器
    session_factory = MagicMock()
    session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    session_factory.return_value.__aexit__ = AsyncMock(return_value=None)

    layer = Layer2HistoryComparison(session_factory, test_run)
    result = await layer.execute()

    assert result["status"] == "baseline"
    assert "current_metrics" in result["data"]
    assert result["data"]["current_metrics"]["p_at_5"] == 0.7
    assert result["data"]["current_metrics"]["r_at_5"] == 0.8
    assert result["data"]["current_metrics"]["f1"] == 0.75
    assert result["data"]["current_metrics"]["mrr"] == 0.6


@pytest.mark.asyncio
async def test_json_diff():
    """JSON 深度对比正确"""
    layer = Layer2HistoryComparison(AsyncMock(), MagicMock())

    old = {"bm25_top_k": 10, "vector_top_k": 10, "nested": {"a": 1, "b": 2}}
    new = {"bm25_top_k": 15, "vector_top_k": 10, "nested": {"a": 1, "b": 3}}

    result = layer._json_diff(old, new)

    assert len(result) == 2
    assert any(
        r["key"] == "bm25_top_k" and r["old_value"] == 10 and r["new_value"] == 15
        for r in result
    )
    assert any(
        r["key"] == "nested.b" and r["old_value"] == 2 and r["new_value"] == 3
        for r in result
    )


@pytest.mark.asyncio
async def test_json_diff_no_changes():
    """JSON 无变化时返回空列表"""
    layer = Layer2HistoryComparison(AsyncMock(), MagicMock())

    old = {"a": 1, "b": 2}
    new = {"a": 1, "b": 2}

    result = layer._json_diff(old, new)

    assert result == []


@pytest.mark.asyncio
async def test_json_diff_new_key():
    """JSON 新增键正确识别"""
    layer = Layer2HistoryComparison(AsyncMock(), MagicMock())

    old = {"a": 1}
    new = {"a": 1, "b": 2}

    result = layer._json_diff(old, new)

    assert len(result) == 1
    assert result[0]["key"] == "b"
    assert result[0]["old_value"] is None
    assert result[0]["new_value"] == 2


@pytest.mark.asyncio
async def test_json_diff_removed_key():
    """JSON 删除键正确识别"""
    layer = Layer2HistoryComparison(AsyncMock(), MagicMock())

    old = {"a": 1, "b": 2}
    new = {"a": 1}

    result = layer._json_diff(old, new)

    assert len(result) == 1
    assert result[0]["key"] == "b"
    assert result[0]["old_value"] == 2
    assert result[0]["new_value"] is None


@pytest.mark.asyncio
async def test_calc_metric_delta():
    """指标变化计算正确"""
    layer = Layer2HistoryComparison(AsyncMock(), MagicMock())

    old_run = MagicMock(
        overall_precision=0.6,
        overall_recall=0.7,
        overall_f1=0.65,
        overall_mrr=0.5,
    )
    new_run = MagicMock(
        overall_precision=0.7,
        overall_recall=0.8,
        overall_f1=0.75,
        overall_mrr=0.6,
    )

    result = layer._calc_metric_delta(old_run, new_run)

    assert result["p_at_5"] == pytest.approx(0.1)
    assert result["r_at_5"] == pytest.approx(0.1)
    assert result["f1"] == pytest.approx(0.1)
    assert result["mrr"] == pytest.approx(0.1)


@pytest.mark.asyncio
async def test_calc_metric_delta_with_none():
    """指标变化计算处理 None 值"""
    layer = Layer2HistoryComparison(AsyncMock(), MagicMock())

    old_run = MagicMock(
        overall_precision=None,
        overall_recall=0.7,
        overall_f1=None,
        overall_mrr=0.5,
    )
    new_run = MagicMock(
        overall_precision=0.7,
        overall_recall=None,
        overall_f1=0.75,
        overall_mrr=None,
    )

    result = layer._calc_metric_delta(old_run, new_run)

    assert result["p_at_5"] == 0.7
    assert result["r_at_5"] == -0.7
    assert result["f1"] == 0.75
    assert result["mrr"] == -0.5


@pytest.mark.asyncio
async def test_get_history_runs_query():
    """获取历史运行的 SQL 查询正确"""
    test_run = MagicMock(
        id="run-1",
        test_set_id="ts-1",
        config_version_id=None,
    )

    session_factory = MagicMock()
    mock_session = AsyncMock()

    mock_prev_run = MagicMock(
        id="run-0",
        status="completed",
        created_at=datetime(2024, 1, 1),
    )
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [mock_prev_run]
    mock_session.execute = AsyncMock(return_value=mock_result)
    session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    session_factory.return_value.__aexit__ = AsyncMock(return_value=None)

    layer = Layer2HistoryComparison(session_factory, test_run)
    history_runs = await layer._get_history_runs(mock_session)

    assert len(history_runs) == 1
    assert history_runs[0].id == "run-0"

    mock_session.execute.assert_called_once()


@pytest.mark.asyncio
async def test_execute_with_history():
    """有历史运行时返回对比分析"""
    test_run = MagicMock(
        id="run-2",
        test_set_id="ts-1",
        config_version_id="config-2",
        overall_precision=0.7,
        overall_recall=0.8,
        overall_f1=0.75,
        overall_mrr=0.6,
    )

    prev_run = MagicMock(
        id="run-1",
        test_set_id="ts-1",
        config_version_id="config-1",
        status="completed",
        created_at=datetime(2024, 1, 1),
        overall_precision=0.6,
        overall_recall=0.7,
        overall_f1=0.65,
        overall_mrr=0.5,
    )

    mock_session = AsyncMock()

    mock_history_result = MagicMock()
    mock_history_result.scalars.return_value.all.return_value = [prev_run]

    mock_config_result = MagicMock()
    mock_config_result.scalar_one_or_none.return_value = None

    mock_badcase_result = MagicMock()
    mock_badcase_result.scalars.return_value.all.return_value = []

    mock_suggestion_result = MagicMock()
    mock_suggestion_result.scalars.return_value.all.return_value = []

    mock_session.execute = AsyncMock(
        side_effect=[
            mock_history_result,
            mock_config_result,
            mock_config_result,
            mock_badcase_result,
            mock_suggestion_result,
        ]
    )

    session_factory = MagicMock()
    session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    session_factory.return_value.__aexit__ = AsyncMock(return_value=None)

    layer = Layer2HistoryComparison(session_factory, test_run)
    result = await layer.execute()

    assert "history_references" in result
    assert result["total_history_runs"] == 1
