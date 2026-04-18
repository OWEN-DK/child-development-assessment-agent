"""规则引擎测试:验证规则从 ConfigManager 加载和触发逻辑"""

import pytest
from unittest.mock import MagicMock, AsyncMock


@pytest.fixture
def mock_config_manager():
    """Mock ConfigManager (包含规则 + 当前参数值)"""
    mgr = MagicMock()
    mgr.get_full_config = MagicMock(
        return_value={
            "rag_tuning_rules": {
                "recall_optimization": {
                    "trigger": {
                        "metric": "overall_recall",
                        "operator": "<",
                        "threshold": 0.7,
                    },
                    "suggestions": [
                        {
                            "param": "rag_hybrid_bm25_top_k",
                            "action": "increase",
                            "suggested_value": 15,
                            "safe_range": [10, 50],
                            "expected_effect": "提升召回率",
                        }
                    ],
                    "priority": "high",
                },
                "precision_optimization": {
                    "trigger": {
                        "metric": "overall_precision",
                        "operator": "<",
                        "threshold": 0.75,
                    },
                    "suggestions": [
                        {
                            "param": "rag_reranker_final_k",
                            "action": "decrease",
                            "suggested_value": 3,
                            "safe_range": [3, 10],
                            "expected_effect": "提升精度",
                        }
                    ],
                    "priority": "high",
                },
                "ranking_optimization": {
                    "trigger": {
                        "metric": "overall_mrr",
                        "operator": "<",
                        "threshold": 0.65,
                    },
                    "suggestions": [
                        {
                            "param": "rag_reranker_initial_k",
                            "action": "increase",
                            "suggested_value": 40,
                            "safe_range": [30, 60],
                            "expected_effect": "提升排序质量",
                        }
                    ],
                    "priority": "medium",
                },
                "comprehensive_optimization": {
                    "trigger": {
                        "or": [
                            {"metric": "overall_f1", "operator": "<", "threshold": 0.6},
                            {
                                "metric": "overall_ndcg",
                                "operator": "<",
                                "threshold": 0.75,
                            },
                        ]
                    },
                    "suggestions": [
                        {
                            "param": "rag_hybrid_merge_mode",
                            "action": "switch",
                            "suggested_value": "AND",
                            "expected_effect": "平衡召回与精度",
                        }
                    ],
                    "priority": "medium",
                },
                "age_adaptation_optimization": {
                    "trigger": {
                        "metric": "age_related_bad_case_ratio",
                        "operator": ">",
                        "threshold": 0.3,
                    },
                    "suggestions": [
                        {
                            "param": "rag_age_filter_strictness",
                            "action": "decrease",
                            "suggested_value": 0.5,
                            "safe_range": [0.3, 0.8],
                            "expected_effect": "降低年龄过滤严格度",
                        }
                    ],
                    "priority": "medium",
                },
                "complex_query_optimization": {
                    "trigger": {
                        "metric": "complex_query_failure_rate",
                        "operator": ">",
                        "threshold": 0.4,
                    },
                    "suggestions": [
                        {
                            "param": "pageindex_enabled",
                            "action": "enable",
                            "suggested_value": True,
                            "expected_effect": "开启 PageIndex",
                        }
                    ],
                    "priority": "high",
                },
                "chunking_optimization": {
                    "trigger": {
                        "metric": "chunking_bad_case_ratio",
                        "operator": ">",
                        "threshold": 0.2,
                    },
                    "suggestions": [
                        {
                            "param": "rag_chunk_size",
                            "action": "increase",
                            "suggested_value": 800,
                            "safe_range": [400, 1200],
                            "expected_effect": "增大分块尺寸",
                        }
                    ],
                    "priority": "medium",
                },
                "performance_optimization": {
                    "trigger": {
                        "metric": "avg_latency_ms",
                        "operator": ">",
                        "threshold": 2000,
                    },
                    "suggestions": [
                        {
                            "param": "rag_max_workers",
                            "action": "increase",
                            "suggested_value": 30,
                            "safe_range": [10, 50],
                            "expected_effect": "增加并行线程数",
                        }
                    ],
                    "priority": "low",
                },
            },
            "rag_hybrid_bm25_top_k": 10,
            "rag_hybrid_vector_top_k": 10,
            "rag_reranker_final_k": 5,
            "rag_reranker_initial_k": 30,
            "rag_hybrid_merge_mode": "OR",
            "rag_age_filter_strictness": 0.7,
            "pageindex_enabled": False,
            "rag_chunk_size": 600,
            "rag_max_workers": 20,
        }
    )
    return mgr


def test_rules_loaded_from_config_manager(mock_config_manager):
    """验证规则从 ConfigManager 正确加载(覆盖全部 8 个规则组)"""
    from src.core.tuning.rule_engine import RuleEngine

    engine = RuleEngine(mock_config_manager)
    rules = engine._load_rules()

    assert "recall_optimization" in rules
    assert "precision_optimization" in rules
    assert "ranking_optimization" in rules
    assert "comprehensive_optimization" in rules
    assert "age_adaptation_optimization" in rules
    assert "complex_query_optimization" in rules
    assert "chunking_optimization" in rules
    assert "performance_optimization" in rules
    assert rules["recall_optimization"]["trigger"]["metric"] == "overall_recall"


@pytest.mark.asyncio
async def test_recall_below_threshold_triggers_suggestion(mock_config_manager):
    """召回率低于阈值时应触发召回优化建议"""
    from src.core.tuning.rule_engine import RuleEngine

    metrics = {"overall_recall": 0.65, "overall_precision": 0.80}
    engine = RuleEngine(mock_config_manager)
    suggestions = await engine.evaluate(metrics)

    # 应包含 rag_hybrid_bm25_top_k 建议
    assert any(s.param_name == "rag_hybrid_bm25_top_k" for s in suggestions)


@pytest.mark.asyncio
async def test_no_trigger_when_metrics_above_threshold(mock_config_manager):
    """指标高于阈值时不应触发建议"""
    from src.core.tuning.rule_engine import RuleEngine

    metrics = {"overall_recall": 0.85, "overall_precision": 0.90}
    engine = RuleEngine(mock_config_manager)
    suggestions = await engine.evaluate(metrics)

    recall_suggestions = [s for s in suggestions if "recall" in s.reason.lower()]
    assert len(recall_suggestions) == 0


@pytest.mark.asyncio
async def test_current_value_from_config_manager(mock_config_manager):
    """建议的当前值应从 ConfigManager 读取(热配置兼容)"""
    from src.core.tuning.rule_engine import RuleEngine

    engine = RuleEngine(mock_config_manager)
    suggestions = await engine.evaluate({"overall_recall": 0.60})

    assert len(suggestions) > 0
    assert suggestions[0].current_value == 10  # 从 ConfigManager 读取
    assert suggestions[0].suggested_value == 15


@pytest.mark.asyncio
async def test_or_trigger_condition(mock_config_manager):
    """OR 条件:任一指标不达标即触发"""
    from src.core.tuning.rule_engine import RuleEngine

    # F1 不达标,NDCG 达标 -> 应触发
    metrics = {"overall_f1": 0.55, "overall_ndcg": 0.80}
    engine = RuleEngine(mock_config_manager)
    suggestions = await engine.evaluate(metrics)

    comprehensive = [s for s in suggestions if s.param_name == "rag_hybrid_merge_mode"]
    assert len(comprehensive) > 0


@pytest.mark.asyncio
async def test_comparison_trigger(mock_config_manager):
    """比较操作符触发:大于阈值"""
    from src.core.tuning.rule_engine import RuleEngine

    metrics = {
        "overall_recall": 0.80,
        "overall_precision": 0.80,
        "age_related_bad_case_ratio": 0.35,
    }
    engine = RuleEngine(mock_config_manager)
    suggestions = await engine.evaluate(metrics)

    age_suggestions = [
        s for s in suggestions if s.param_name == "rag_age_filter_strictness"
    ]
    assert len(age_suggestions) > 0


@pytest.mark.asyncio
async def test_performance_trigger(mock_config_manager):
    """性能指标触发"""
    from src.core.tuning.rule_engine import RuleEngine

    metrics = {
        "overall_recall": 0.80,
        "overall_precision": 0.80,
        "avg_latency_ms": 2500,
    }
    engine = RuleEngine(mock_config_manager)
    suggestions = await engine.evaluate(metrics)

    perf_suggestions = [s for s in suggestions if s.param_name == "rag_max_workers"]
    assert len(perf_suggestions) > 0
    assert perf_suggestions[0].priority == "low"
