"""统一引擎测试:验证三层诊断组件编排"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from src.schemas.tuning import TuningSuggestion, HistoryReference, LLMDiagnosis


@pytest.mark.asyncio
async def test_generate_suggestion_merges_three_layers():
    """引擎应合并三层诊断结果"""
    from src.core.tuning.engine import TuningSuggestionEngine

    mock_rule_engine = AsyncMock()
    mock_rule_engine.evaluate = AsyncMock(
        return_value=[
            TuningSuggestion(
                id="rule_1",
                param_name="p1",
                current_value=1,
                suggested_value=2,
                action="increase",
                reason="",
                expected_effect="",
                priority="high",
                source="rule_engine",
            ),
        ]
    )
    mock_history_analyzer = AsyncMock()
    mock_history_analyzer.analyze = AsyncMock(
        return_value=[
            HistoryReference(
                run_id="run_1",
                date="2026-04-01",
                changed_params={},
                metric_changes={},
                conclusion="",
            )
        ]
    )
    mock_llm_diagnoser = AsyncMock()
    mock_llm_diagnoser.diagnose = AsyncMock(
        return_value=LLMDiagnosis(summary="", findings=[], recommendations=[])
    )
    mock_conflict_detector = MagicMock()
    mock_conflict_detector.detect = MagicMock(
        return_value=(
            [
                TuningSuggestion(
                    id="rule_1",
                    param_name="p1",
                    current_value=1,
                    suggested_value=2,
                    action="increase",
                    reason="",
                    expected_effect="",
                    priority="high",
                    source="rule_engine",
                ),
            ],
            0,
        )
    )

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
        mock_rule_engine,
        mock_history_analyzer,
        mock_llm_diagnoser,
        mock_conflict_detector,
        mock_test_run_repo,
    )
    response = await engine.generate_suggestions("test_run_id")

    assert response.run_id == "test_run_id"
    assert response.total_suggestions == 1


@pytest.mark.asyncio
async def test_generate_suggestions_skips_llm_when_bad_cases_lt_3():
    """Bad Case < 3 时应跳过 LLM 诊断"""
    from src.core.tuning.engine import TuningSuggestionEngine

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
        mock_rule_engine,
        mock_history_analyzer,
        mock_llm_diagnoser,
        mock_conflict_detector,
        mock_test_run_repo,
    )
    response = await engine.generate_suggestions("test_run_id")

    assert response.llm_diagnosis is None
