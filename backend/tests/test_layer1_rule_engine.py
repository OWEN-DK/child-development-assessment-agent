import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from src.core.validation.layers.layer1_rule_engine import Layer1RuleEngine


def _make_session_factory_mock(mock_session):
    """创建支持 async with 的 session factory mock"""
    mock_cm = MagicMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_session)
    mock_cm.__aexit__ = AsyncMock(return_value=None)
    return MagicMock(return_value=mock_cm)


@pytest.mark.asyncio
async def test_adaptive_step():
    """自适应步长计算正确"""
    engine = Layer1RuleEngine(session_factory=AsyncMock(), test_run=MagicMock())

    assert engine._calc_adaptive_step("bm25_top_k", 10) == 3
    assert engine._calc_adaptive_step("bm25_top_k", 20) == 5
    assert engine._calc_adaptive_step("bm25_top_k", 2) == 1


@pytest.mark.asyncio
async def test_clamp_param():
    """参数限制在安全范围内"""
    engine = Layer1RuleEngine(session_factory=AsyncMock(), test_run=MagicMock())

    assert engine._clamp_param("bm25_top_k", 100) == 50
    assert engine._clamp_param("bm25_top_k", 0) == 5
    assert engine._clamp_param("fusion_threshold", 0.01) == 0.1


@pytest.mark.asyncio
async def test_detect_conflicts_same_direction():
    """同方向冲突取较大值"""
    engine = Layer1RuleEngine(session_factory=AsyncMock(), test_run=MagicMock())
    suggestions = [
        {
            "param": "bm25_top_k",
            "current": 10,
            "suggested": 15,
            "reason": "P@5 不达标",
            "priority": "param_tuning",
        },
        {
            "param": "bm25_top_k",
            "current": 10,
            "suggested": 20,
            "reason": "R@5 不达标",
            "priority": "param_tuning",
        },
    ]
    result = engine._detect_conflicts(suggestions)
    assert len(result) == 1
    assert result[0]["suggested"] == 20


@pytest.mark.asyncio
async def test_detect_conflicts_opposite_direction():
    """相反方向冲突标记 conflict=True"""
    engine = Layer1RuleEngine(session_factory=AsyncMock(), test_run=MagicMock())
    suggestions = [
        {
            "param": "fusion_threshold",
            "current": 0.25,
            "suggested": 0.30,
            "reason": "F1 偏低",
            "priority": "param_tuning",
        },
        {
            "param": "fusion_threshold",
            "current": 0.25,
            "suggested": 0.20,
            "reason": "F1 偏高",
            "priority": "param_tuning",
        },
    ]
    result = engine._detect_conflicts(suggestions)
    assert len(result) == 1
    assert result[0].get("conflict") is True
    assert "conflict_warning" in result[0]


@pytest.mark.asyncio
async def test_check_safe_ranges():
    """参数超出安全范围时生成建议"""
    engine = Layer1RuleEngine(session_factory=AsyncMock(), test_run=MagicMock())
    config = {"bm25_top_k": 100, "fusion_threshold": 0.01}
    result = engine._check_safe_ranges(config)
    assert len(result) == 2
    assert result[0]["param"] == "bm25_top_k"
    assert result[0]["suggested"] == 50
    assert result[1]["param"] == "fusion_threshold"
    assert result[1]["suggested"] == 0.1


@pytest.mark.asyncio
async def test_priority_ordering():
    """建议排序：安全范围 > 功能开关 > 参数调优"""
    engine = Layer1RuleEngine(session_factory=AsyncMock(), test_run=MagicMock())
    suggestions = [
        {
            "param": "c",
            "current": 1,
            "suggested": 2,
            "reason": "test",
            "priority": "param_tuning",
        },
        {
            "param": "a",
            "current": 1,
            "suggested": 2,
            "reason": "test",
            "priority": "safe_range",
        },
        {
            "param": "b",
            "current": False,
            "suggested": True,
            "reason": "test",
            "priority": "function_switch",
        },
    ]
    priority_order = {"safe_range": 0, "function_switch": 1, "param_tuning": 2}
    suggestions.sort(key=lambda s: priority_order.get(s["priority"], 3))
    assert suggestions[0]["priority"] == "safe_range"
    assert suggestions[1]["priority"] == "function_switch"
    assert suggestions[2]["priority"] == "param_tuning"


@pytest.mark.asyncio
async def test_execute_all_metrics_pass():
    """所有指标达标且功能开关已开启时无建议"""
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_run = MagicMock()
    mock_run.overall_precision = 0.80
    mock_run.overall_recall = 0.90
    mock_run.overall_f1 = 0.85
    mock_run.overall_mrr = 0.80
    mock_run.overall_ndcg = 0.85
    mock_run.config_version_id = None
    mock_result.scalar_one_or_none.return_value = mock_run
    mock_session.execute.return_value = mock_result

    mock_session_factory = _make_session_factory_mock(mock_session)
    test_run = MagicMock()
    test_run.id = "test-run-1"
    test_run.config_version_id = None

    with patch(
        "src.core.validation.layers.layer1_rule_engine._get_layer1_config"
    ) as mock_config:
        mock_config.return_value = {
            "thresholds": {
                "p_at_5": 0.70,
                "r_at_5": 0.85,
                "f1": 0.75,
                "mrr": 0.70,
                "short_query_failure_rate": 0.30,
                "cross_domain_failure_rate": 0.20,
            },
            "param_safe_ranges": {},
        }

        engine = Layer1RuleEngine(
            session_factory=mock_session_factory, test_run=test_run
        )
        engine._get_rag_config = AsyncMock(
            return_value={
                "pageindex_enabled": True,
                "query_rewrite_enabled": True,
                "synonym_expansion_enabled": True,
            }
        )
        result = await engine.execute()

        assert result["rules_triggered"] == 0
        assert result["suggestions"] == []


@pytest.mark.asyncio
async def test_execute_p_at_5_below_threshold():
    """P@5 不达标时生成参数调优建议"""
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_run = MagicMock()
    mock_run.overall_precision = 0.50
    mock_run.overall_recall = 0.80
    mock_run.overall_f1 = 0.85
    mock_run.overall_mrr = 0.80
    mock_run.overall_ndcg = 0.85
    mock_run.config_version_id = None
    mock_result.scalar_one_or_none.return_value = mock_run
    mock_session.execute.return_value = mock_result

    mock_session_factory = _make_session_factory_mock(mock_session)
    test_run = MagicMock()
    test_run.id = "test-run-1"
    test_run.config_version_id = None

    with patch(
        "src.core.validation.layers.layer1_rule_engine._get_layer1_config"
    ) as mock_config:
        mock_config.return_value = {
            "thresholds": {
                "p_at_5": 0.70,
                "r_at_5": 0.85,
                "f1": 0.75,
                "mrr": 0.70,
                "short_query_failure_rate": 0.30,
                "cross_domain_failure_rate": 0.20,
            },
            "param_safe_ranges": {},
        }

        engine = Layer1RuleEngine(
            session_factory=mock_session_factory, test_run=test_run
        )
        result = await engine.execute()

        params = [s["param"] for s in result["suggestions"]]
        assert "bm25_top_k" in params
        assert "vector_top_k" in params


@pytest.mark.asyncio
async def test_execute_short_query_failure():
    """短查询失败率超标且未开启重写时生成功能开关建议"""
    mock_session = AsyncMock()
    mock_session_factory = _make_session_factory_mock(mock_session)
    test_run = MagicMock()
    test_run.id = "test-run-1"

    with patch(
        "src.core.validation.layers.layer1_rule_engine._get_layer1_config"
    ) as mock_config:
        mock_config.return_value = {
            "thresholds": {
                "p_at_5": 0.70,
                "r_at_5": 0.85,
                "f1": 0.75,
                "mrr": 0.70,
                "short_query_failure_rate": 0.30,
                "cross_domain_failure_rate": 0.20,
            },
            "param_safe_ranges": {},
        }

        engine = Layer1RuleEngine(
            session_factory=mock_session_factory, test_run=test_run
        )
        engine._get_metrics = AsyncMock(
            return_value={
                "short_query_failure_rate": 0.50,
                "p_at_5": 0.80,
                "r_at_5": 0.90,
                "f1": 0.85,
                "mrr": 0.80,
                "ndcg": 0.85,
            }
        )
        engine._get_rag_config = AsyncMock(
            return_value={"query_rewrite_enabled": False}
        )
        result = await engine.execute()

        params = [s["param"] for s in result["suggestions"]]
        assert "query_rewrite_enabled" in params


@pytest.mark.asyncio
async def test_execute_cross_domain_failure():
    """跨领域失败率超标且未开启同义词扩展时生成功能开关建议"""
    mock_session = AsyncMock()
    mock_session_factory = _make_session_factory_mock(mock_session)
    test_run = MagicMock()
    test_run.id = "test-run-1"

    with patch(
        "src.core.validation.layers.layer1_rule_engine._get_layer1_config"
    ) as mock_config:
        mock_config.return_value = {
            "thresholds": {
                "p_at_5": 0.70,
                "r_at_5": 0.85,
                "f1": 0.75,
                "mrr": 0.70,
                "short_query_failure_rate": 0.30,
                "cross_domain_failure_rate": 0.20,
            },
            "param_safe_ranges": {},
        }

        engine = Layer1RuleEngine(
            session_factory=mock_session_factory, test_run=test_run
        )
        engine._get_metrics = AsyncMock(
            return_value={
                "cross_domain_failure_rate": 0.40,
                "p_at_5": 0.80,
                "r_at_5": 0.90,
                "f1": 0.85,
                "mrr": 0.80,
                "ndcg": 0.85,
            }
        )
        engine._get_rag_config = AsyncMock(
            return_value={"synonym_expansion_enabled": False}
        )
        result = await engine.execute()

        params = [s["param"] for s in result["suggestions"]]
        assert "synonym_expansion_enabled" in params


@pytest.mark.asyncio
async def test_execute_pageindex_not_enabled():
    """PageIndex 未启用时生成建议"""
    mock_session = AsyncMock()
    mock_session_factory = _make_session_factory_mock(mock_session)
    test_run = MagicMock()
    test_run.id = "test-run-1"

    with patch(
        "src.core.validation.layers.layer1_rule_engine._get_layer1_config"
    ) as mock_config:
        mock_config.return_value = {
            "thresholds": {
                "p_at_5": 0.70,
                "r_at_5": 0.85,
                "f1": 0.75,
                "mrr": 0.70,
                "short_query_failure_rate": 0.30,
                "cross_domain_failure_rate": 0.20,
            },
            "param_safe_ranges": {},
        }

        engine = Layer1RuleEngine(
            session_factory=mock_session_factory, test_run=test_run
        )
        engine._get_metrics = AsyncMock(
            return_value={
                "p_at_5": 0.80,
                "r_at_5": 0.90,
                "f1": 0.85,
                "mrr": 0.80,
                "ndcg": 0.85,
            }
        )
        engine._get_rag_config = AsyncMock(return_value={"pageindex_enabled": False})
        result = await engine.execute()

        params = [s["param"] for s in result["suggestions"]]
        assert "pageindex_enabled" in params
