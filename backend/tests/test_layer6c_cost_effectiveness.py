import pytest
from unittest.mock import MagicMock, AsyncMock
from src.core.validation.layers.layer6c_cost_effectiveness import (
    Layer6cCostEffectiveness,
)


def make_session_factory_for_6c(prev_run=None):
    """为 Layer 6c 创建 session_factory mock，返回上一次运行记录"""
    mock_session = AsyncMock()

    async def mock_execute(stmt):
        mock_scalars = MagicMock()
        mock_scalars.first.return_value = prev_run
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars
        return mock_result

    mock_session.execute = mock_execute
    session_factory = MagicMock()
    session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    session_factory.return_value.__aexit__ = AsyncMock(return_value=None)
    return session_factory


def make_test_run(run_id, test_set_id, config_version_id, config_snapshot, **metrics):
    """构造 test_run mock，包含 config_version 关系"""
    test_run = MagicMock(
        id=run_id,
        test_set_id=test_set_id,
        config_version_id=config_version_id,
    )
    test_run.config_version = MagicMock(config_snapshot=config_snapshot)
    for key, value in metrics.items():
        setattr(test_run, key, value)
    return test_run


def make_prev_run(run_id, config_version_id, config_snapshot, **metrics):
    """构造 prev_run mock，包含 config_version 关系"""
    prev_run = MagicMock(
        id=run_id,
        config_version_id=config_version_id,
    )
    prev_run.config_version = MagicMock(config_snapshot=config_snapshot)
    for key, value in metrics.items():
        setattr(prev_run, key, value)
    return prev_run


@pytest.mark.asyncio
async def test_no_previous_run_skipped():
    """无上一次运行时跳过"""
    test_run = make_test_run(
        "run-2",
        "ts-1",
        "cv-2",
        {"bm25_top_k": 15},
        overall_precision=0.8,
        overall_recall=0.85,
        overall_f1=0.82,
        overall_mrr=0.75,
        overall_ndcg=0.80,
        total_tokens=1000,
    )
    session_factory = make_session_factory_for_6c(prev_run=None)

    layer = Layer6cCostEffectiveness(session_factory, test_run)
    result = await layer.execute()
    assert result["status"] == "skipped"


@pytest.mark.asyncio
async def test_config_not_changed_skipped():
    """配置未变更时跳过"""
    test_run = make_test_run(
        "run-2",
        "ts-1",
        "cv-1",
        {"bm25_top_k": 10},
        overall_precision=0.8,
        overall_recall=0.85,
        overall_f1=0.82,
        overall_mrr=0.75,
        overall_ndcg=0.80,
        total_tokens=1000,
    )
    prev_run = make_prev_run(
        "run-1",
        "cv-1",
        {"bm25_top_k": 10},
        overall_precision=0.7,
        overall_recall=0.75,
        overall_f1=0.72,
        overall_mrr=0.65,
        overall_ndcg=0.70,
        total_tokens=1000,
    )
    session_factory = make_session_factory_for_6c(prev_run=prev_run)

    layer = Layer6cCostEffectiveness(session_factory, test_run)
    result = await layer.execute()
    assert result["status"] == "skipped"


@pytest.mark.asyncio
async def test_zero_cost_scenario():
    """零成本场景特殊处理"""
    test_run = make_test_run(
        "run-2",
        "ts-1",
        "cv-2",
        {"bm25_top_k": 15},
        overall_precision=0.8,
        overall_recall=0.85,
        overall_f1=0.82,
        overall_mrr=0.75,
        overall_ndcg=0.80,
        total_tokens=1000,
    )
    prev_run = make_prev_run(
        "run-1",
        "cv-1",
        {"bm25_top_k": 10},
        overall_precision=0.7,
        overall_recall=0.75,
        overall_f1=0.72,
        overall_mrr=0.65,
        overall_ndcg=0.70,
        total_tokens=1000,
    )
    session_factory = make_session_factory_for_6c(prev_run=prev_run)

    layer = Layer6cCostEffectiveness(session_factory, test_run)
    result = await layer.execute()

    assert result["status"] == "completed"
    assert result["data"]["extra_tokens"] == 0
    assert result["data"]["cost_effectiveness_ratio"] > 0


@pytest.mark.asyncio
async def test_metric_improvement_positive():
    """指标提升时得分为正"""
    test_run = make_test_run(
        "run-2",
        "ts-1",
        "cv-2",
        {"top_k": 15},
        overall_precision=0.8,
        overall_recall=0.8,
        overall_f1=0.8,
        overall_mrr=0.8,
        overall_ndcg=0.8,
        total_tokens=1000,
    )
    prev_run = make_prev_run(
        "run-1",
        "cv-1",
        {"top_k": 10},
        overall_precision=0.7,
        overall_recall=0.7,
        overall_f1=0.7,
        overall_mrr=0.7,
        overall_ndcg=0.7,
        total_tokens=1000,
    )
    session_factory = make_session_factory_for_6c(prev_run=prev_run)

    layer = Layer6cCostEffectiveness(session_factory, test_run)
    result = await layer.execute()

    assert result["data"]["metric_improvement_score"] > 0


@pytest.mark.asyncio
async def test_config_changes_extracted():
    """配置变更正确提取"""
    test_run = make_test_run(
        "run-2",
        "ts-1",
        "cv-2",
        {"bm25_top_k": 15, "new_param": True},
        overall_precision=0.8,
        overall_recall=0.8,
        overall_f1=0.8,
        overall_mrr=0.8,
        overall_ndcg=0.8,
        total_tokens=1000,
    )
    prev_run = make_prev_run(
        "run-1",
        "cv-1",
        {"bm25_top_k": 10, "old_param": False},
        overall_precision=0.7,
        overall_recall=0.7,
        overall_f1=0.7,
        overall_mrr=0.7,
        overall_ndcg=0.7,
        total_tokens=1000,
    )
    session_factory = make_session_factory_for_6c(prev_run=prev_run)

    layer = Layer6cCostEffectiveness(session_factory, test_run)
    result = await layer.execute()

    changes = result["data"]["config_changes"]
    assert any(c["key"] == "bm25_top_k" for c in changes)
    assert any(c["key"] == "new_param" for c in changes)
    assert any(c["key"] == "old_param" for c in changes)


@pytest.mark.asyncio
async def test_recommendation_based_on_ratio():
    """根据比率给出建议"""
    test_run = make_test_run(
        "run-2",
        "ts-1",
        "cv-2",
        {"top_k": 20},
        overall_precision=0.9,
        overall_recall=0.9,
        overall_f1=0.9,
        overall_mrr=0.9,
        overall_ndcg=0.9,
        total_tokens=500,
    )
    prev_run = make_prev_run(
        "run-1",
        "cv-1",
        {"top_k": 10},
        overall_precision=0.5,
        overall_recall=0.5,
        overall_f1=0.5,
        overall_mrr=0.5,
        overall_ndcg=0.5,
        total_tokens=1000,
    )
    session_factory = make_session_factory_for_6c(prev_run=prev_run)

    layer = Layer6cCostEffectiveness(session_factory, test_run)
    result = await layer.execute()

    assert "recommendation" in result["data"]
    assert isinstance(result["data"]["recommendation"], str)
