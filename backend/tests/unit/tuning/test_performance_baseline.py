"""性能基线测试：验证各组件响应时间符合验收标准"""

import pytest
import time
from unittest.mock import MagicMock, AsyncMock


@pytest.fixture
def mock_config_manager():
    """Mock ConfigManager"""
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
            "rag_reranker_final_k": 5,
        }
    )
    return mgr


@pytest.mark.asyncio
async def test_rule_engine_latency(mock_config_manager):
    """规则引擎响应时间应 <50ms"""
    from src.core.tuning.rule_engine import RuleEngine

    engine = RuleEngine(mock_config_manager)
    metrics = {
        "overall_recall": 0.60,
        "overall_precision": 0.70,
        "overall_f1": 0.55,
        "overall_mrr": 0.60,
        "overall_ndcg": 0.70,
        "age_related_bad_case_ratio": 0.35,
        "complex_query_failure_rate": 0.45,
        "chunking_bad_case_ratio": 0.25,
        "avg_latency_ms": 2500,
    }

    start = time.perf_counter()
    suggestions = await engine.evaluate(metrics)
    elapsed_ms = (time.perf_counter() - start) * 1000

    assert elapsed_ms < 50, f"规则引擎响应时间 {elapsed_ms:.1f}ms 超过 50ms 基线"
    assert len(suggestions) > 0


@pytest.mark.asyncio
async def test_history_analyzer_latency():
    """历史对比分析响应时间应 <100ms (≥5 次历史运行)"""
    from src.core.tuning.history_analyzer import HistoryAnalyzer

    mock_runs = [
        MagicMock(
            id=f"run_{i}",
            config_version_id=f"v{i}",
            previous_config_version_id=f"v{i - 1}" if i > 0 else None,
            overall_recall=0.60 + i * 0.05,
            overall_precision=0.80,
            overall_f1=0.65,
            overall_mrr=0.60,
            overall_ndcg=0.70,
            created_at=MagicMock(strftime=MagicMock(return_value="2026-04-01")),
        )
        for i in range(5)
    ]

    mock_test_run_repo = AsyncMock()
    mock_test_run_repo.get_completed_runs = AsyncMock(return_value=mock_runs)

    mock_config_manager = AsyncMock()
    mock_config_manager.get_version_config = AsyncMock(
        return_value={"rag_hybrid_bm25_top_k": 10}
    )

    analyzer = HistoryAnalyzer(mock_test_run_repo, mock_config_manager)

    start = time.perf_counter()
    references = await analyzer.analyze(
        current_metrics={"overall_recall": 0.65},
        current_run_id="current_run",
    )
    elapsed_ms = (time.perf_counter() - start) * 1000

    assert elapsed_ms < 100, f"历史分析响应时间 {elapsed_ms:.1f}ms 超过 100ms 基线"


@pytest.mark.asyncio
async def test_cache_hit_rate():
    """同一 run_id 连续请求 5 次，缓存应生效 (调用次数 ≤ 1)"""
    from src.core.tuning.engine import TuningSuggestionEngine
    from src.core.tuning.conflict_detector import ConflictDetector

    mock_rule_engine = AsyncMock()
    mock_rule_engine.evaluate = AsyncMock(return_value=[])

    mock_history_analyzer = AsyncMock()
    mock_history_analyzer.analyze = AsyncMock(return_value=[])

    mock_llm_diagnoser = AsyncMock()
    mock_llm_diagnoser.diagnose = AsyncMock(return_value=None)

    mock_conflict_detector = MagicMock()
    mock_conflict_detector.detect = MagicMock(return_value=([], 0))

    mock_test_run_repo = AsyncMock()
    mock_test_run = MagicMock(
        id="test_run_1",
        overall_precision=0.8,
        overall_recall=0.7,
        overall_f1=0.75,
        overall_mrr=0.7,
        overall_ndcg=0.8,
    )
    mock_test_run_repo.get_by_id = AsyncMock(return_value=mock_test_run)
    mock_test_run_repo.get_results = AsyncMock(return_value=[])

    engine = TuningSuggestionEngine(
        rule_engine=mock_rule_engine,
        history_analyzer=mock_history_analyzer,
        llm_diagnoser=mock_llm_diagnoser,
        conflict_detector=mock_conflict_detector,
        test_run_repo=mock_test_run_repo,
    )

    for _ in range(5):
        await engine.generate_suggestions("test_run_1")

    assert mock_rule_engine.evaluate.call_count == 1, (
        f"规则引擎被调用 {mock_rule_engine.evaluate.call_count} 次，缓存未生效"
    )
    assert mock_history_analyzer.analyze.call_count == 1, (
        f"历史分析器被调用 {mock_history_analyzer.analyze.call_count} 次，缓存未生效"
    )


@pytest.mark.asyncio
async def test_conflict_detector_latency():
    """冲突检测响应时间应 <10ms"""
    from src.core.tuning.conflict_detector import ConflictDetector
    from src.model.tuning import TuningSuggestion

    suggestions = [
        TuningSuggestion(
            param_name=f"param_{i}",
            action="increase" if i % 2 == 0 else "decrease",
            priority="high",
            source="rule_engine",
            current_value=10,
            suggested_value=15,
            reason="",
            expected_effect="",
        )
        for i in range(20)
    ]

    detector = ConflictDetector()

    start = time.perf_counter()
    filtered, count = detector.detect(suggestions)
    elapsed_ms = (time.perf_counter() - start) * 1000

    assert elapsed_ms < 10, f"冲突检测响应时间 {elapsed_ms:.1f}ms 超过 10ms 基线"
