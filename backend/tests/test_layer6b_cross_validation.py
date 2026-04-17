import pytest
from unittest.mock import MagicMock, AsyncMock
from src.core.validation.layers.layer6b_cross_validation import Layer6bCrossValidation


def make_session_factory_for_6b(test_results_data):
    """为 Layer 6b 创建 session_factory mock，返回 (test_result, test_case) 行"""
    mock_session = AsyncMock()

    async def mock_execute(stmt):
        mock_scalars = MagicMock()
        rows = []
        for data in test_results_data:
            mock_result = MagicMock()
            mock_result.hit_at_1 = data.get("hit_at_1", 0)
            mock_result.hit_at_3 = data.get("hit_at_3", 0)
            mock_result.hit_at_5 = data.get("hit_at_5", 0)
            mock_case = MagicMock()
            mock_case.domain = MagicMock(value=data.get("domain", "unknown"))
            mock_case.age_months = data.get("age_months")
            rows.append((mock_result, mock_case))
        mock_scalars.all.return_value = rows
        mock_result_obj = MagicMock()
        mock_result_obj.scalars.return_value = mock_scalars
        mock_result_obj.all.return_value = rows
        return mock_result_obj

    mock_session.execute = mock_execute
    session_factory = MagicMock()
    session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    session_factory.return_value.__aexit__ = AsyncMock(return_value=None)
    return session_factory


@pytest.mark.asyncio
async def test_missing_results_skipped():
    """缺少测试结果时跳过"""
    session_factory = make_session_factory_for_6b([])
    test_run = MagicMock(id="run-1")
    layer = Layer6bCrossValidation(session_factory, test_run)
    result = await layer.execute()
    assert result["status"] == "skipped"


@pytest.mark.asyncio
async def test_underperforming_domain():
    """某领域 F1 低于平均时警告"""
    # 构造数据：motor 领域高，language 领域低
    test_results_data = [
        {
            "domain": "motor",
            "age_months": 30,
            "hit_at_1": 1,
            "hit_at_3": 1,
            "hit_at_5": 1,
        },
        {
            "domain": "motor",
            "age_months": 30,
            "hit_at_1": 1,
            "hit_at_3": 1,
            "hit_at_5": 0,
        },
        {
            "domain": "language",
            "age_months": 54,
            "hit_at_1": 0,
            "hit_at_3": 0,
            "hit_at_5": 1,
        },
    ]
    session_factory = make_session_factory_for_6b(test_results_data)
    test_run = MagicMock(id="run-1")
    layer = Layer6bCrossValidation(session_factory, test_run)
    result = await layer.execute()

    assert len(result["data"]["underperforming_domains"]) > 0
    assert any(
        "language" in d["domain"] for d in result["data"]["underperforming_domains"]
    )


@pytest.mark.asyncio
async def test_consistency_score_calculation():
    """一致性评分计算正确"""
    test_results_data = [
        {
            "domain": "motor",
            "age_months": 30,
            "hit_at_1": 1,
            "hit_at_3": 1,
            "hit_at_5": 0,
        },
        {
            "domain": "language",
            "age_months": 54,
            "hit_at_1": 1,
            "hit_at_3": 0,
            "hit_at_5": 1,
        },
    ]
    session_factory = make_session_factory_for_6b(test_results_data)
    test_run = MagicMock(id="run-1")
    layer = Layer6bCrossValidation(session_factory, test_run)
    result = await layer.execute()

    assert 0 <= result["data"]["consistency_score"] <= 1


@pytest.mark.asyncio
async def test_domain_and_age_group_metrics():
    """领域和年龄组指标计算正确"""
    test_results_data = [
        {
            "domain": "motor",
            "age_months": 30,
            "hit_at_1": 1,
            "hit_at_3": 1,
            "hit_at_5": 0,
        },
        {
            "domain": "motor",
            "age_months": 30,
            "hit_at_1": 0,
            "hit_at_3": 1,
            "hit_at_5": 1,
        },
        {
            "domain": "language",
            "age_months": 54,
            "hit_at_1": 1,
            "hit_at_3": 1,
            "hit_at_5": 1,
        },
    ]
    session_factory = make_session_factory_for_6b(test_results_data)
    test_run = MagicMock(id="run-1")
    layer = Layer6bCrossValidation(session_factory, test_run)
    result = await layer.execute()

    assert "motor" in result["data"]["domain_metrics"]
    assert "language" in result["data"]["domain_metrics"]
    assert "13-36月" in result["data"]["age_group_metrics"]
    assert "37-72月" in result["data"]["age_group_metrics"]
    # motor: (2/3 + 2/3) / 2 = 2/3 ≈ 0.667
    assert abs(result["data"]["domain_metrics"]["motor"] - 2 / 3) < 0.01


@pytest.mark.asyncio
async def test_no_underperforming_when_balanced():
    """所有领域均衡时无警告"""
    test_results_data = [
        {
            "domain": "motor",
            "age_months": 30,
            "hit_at_1": 1,
            "hit_at_3": 1,
            "hit_at_5": 0,
        },
        {
            "domain": "language",
            "age_months": 54,
            "hit_at_1": 1,
            "hit_at_3": 1,
            "hit_at_5": 0,
        },
        {
            "domain": "social",
            "age_months": 42,
            "hit_at_1": 1,
            "hit_at_3": 1,
            "hit_at_5": 0,
        },
    ]
    session_factory = make_session_factory_for_6b(test_results_data)
    test_run = MagicMock(id="run-1")
    layer = Layer6bCrossValidation(session_factory, test_run)
    result = await layer.execute()

    assert len(result["data"]["underperforming_domains"]) == 0


@pytest.mark.asyncio
async def test_warnings_for_low_consistency():
    """一致性低时产生警告"""
    test_results_data = [
        {
            "domain": "motor",
            "age_months": 30,
            "hit_at_1": 1,
            "hit_at_3": 1,
            "hit_at_5": 1,
        },
        {
            "domain": "language",
            "age_months": 54,
            "hit_at_1": 0,
            "hit_at_3": 0,
            "hit_at_5": 1,
        },
    ]
    session_factory = make_session_factory_for_6b(test_results_data)
    test_run = MagicMock(id="run-1")
    layer = Layer6bCrossValidation(session_factory, test_run)
    result = await layer.execute()

    warnings = result["data"]["warnings"]
    assert any("一致性" in w["message"] for w in warnings)
