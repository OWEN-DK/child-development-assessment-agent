"""调参建议引擎集成测试"""

import pytest
from unittest.mock import MagicMock, AsyncMock
from src.core.tuning.engine import TuningSuggestionEngine
from src.core.tuning.rule_engine import RuleEngine
from src.core.tuning.history_analyzer import HistoryAnalyzer
from src.core.tuning.llm_diagnoser import LLMDiagnoser
from src.core.tuning.conflict_detector import ConflictDetector
from src.schemas.tuning import TuningSuggestion, HistoryReference, LLMDiagnosis


@pytest.fixture
def mock_components():
    """Mock 所有依赖组件"""
    mock_rule_engine = AsyncMock()
    mock_history_analyzer = AsyncMock()
    mock_llm_diagnoser = AsyncMock()
    mock_conflict_detector = MagicMock()
    mock_test_run_repo = AsyncMock()

    return {
        "rule_engine": mock_rule_engine,
        "history_analyzer": mock_history_analyzer,
        "llm_diagnoser": mock_llm_diagnoser,
        "conflict_detector": mock_conflict_detector,
        "test_run_repo": mock_test_run_repo,
    }


@pytest.mark.asyncio
async def test_full_tuning_workflow(mock_components):
    """完整调参建议工作流: 测试完成 → 获取建议 → 冲突检测 → 返回结果"""
    mock_components["rule_engine"].evaluate = AsyncMock(
        return_value=[
            TuningSuggestion(
                id="rule_1",
                param_name="rag_hybrid_bm25_top_k",
                current_value=10,
                suggested_value=15,
                action="increase",
                reason="recall_optimization 规则触发",
                expected_effect="扩大 BM25 检索范围",
                priority="high",
                source="rule_engine",
                safe_range=(10, 50),
            ),
            TuningSuggestion(
                id="rule_2",
                param_name="rag_reranker_final_k",
                current_value=5,
                suggested_value=3,
                action="decrease",
                reason="precision_optimization 规则触发",
                expected_effect="提升精度",
                priority="high",
                source="rule_engine",
                safe_range=(3, 10),
            ),
        ]
    )

    mock_components["history_analyzer"].analyze = AsyncMock(
        return_value=[
            HistoryReference(
                run_id="run_prev_1",
                date="2026-04-10",
                changed_params={"rag_hybrid_bm25_top_k": {"from": 8, "to": 10}},
                metric_changes={
                    "overall_recall": {"from": 0.65, "to": 0.72, "delta": "+0.07"}
                },
                conclusion="修改 top_k 从 8 到 10 后，overall_recall 变化了 +0.0700",
            )
        ]
    )

    mock_components["llm_diagnoser"].diagnose = AsyncMock(return_value=None)

    mock_components["conflict_detector"].detect = MagicMock(
        return_value=(
            [
                TuningSuggestion(
                    id="rule_1",
                    param_name="rag_hybrid_bm25_top_k",
                    current_value=10,
                    suggested_value=15,
                    action="increase",
                    reason="recall_optimization 规则触发",
                    expected_effect="扩大 BM25 检索范围",
                    priority="high",
                    source="rule_engine",
                    safe_range=(10, 50),
                ),
                TuningSuggestion(
                    id="rule_2",
                    param_name="rag_reranker_final_k",
                    current_value=5,
                    suggested_value=3,
                    action="decrease",
                    reason="precision_optimization 规则触发",
                    expected_effect="提升精度",
                    priority="high",
                    source="rule_engine",
                    safe_range=(3, 10),
                ),
            ],
            0,
        )
    )

    mock_components["test_run_repo"].get_by_id = AsyncMock(
        return_value=MagicMock(
            id="test_run_1",
            overall_precision=0.70,
            overall_recall=0.65,
            overall_f1=0.67,
            overall_mrr=0.60,
            overall_ndcg=0.70,
        )
    )
    mock_components["test_run_repo"].get_results = AsyncMock(return_value=[])

    engine = TuningSuggestionEngine(
        rule_engine=mock_components["rule_engine"],
        history_analyzer=mock_components["history_analyzer"],
        llm_diagnoser=mock_components["llm_diagnoser"],
        conflict_detector=mock_components["conflict_detector"],
        test_run_repo=mock_components["test_run_repo"],
    )

    response = await engine.generate_suggestions("test_run_1")

    assert response.run_id == "test_run_1"
    assert response.total_suggestions == 2
    assert len(response.rule_engine_suggestions) == 2
    assert len(response.history_references) == 1
    assert response.llm_diagnosis is None
    assert response.conflict_filtered_count == 0


@pytest.mark.asyncio
async def test_tuning_workflow_with_llm_diagnosis(mock_components):
    """包含 LLM 诊断的完整工作流"""
    mock_components["rule_engine"].evaluate = AsyncMock(
        return_value=[
            TuningSuggestion(
                id="rule_1",
                param_name="rag_hybrid_bm25_top_k",
                current_value=10,
                suggested_value=15,
                action="increase",
                reason="recall_optimization 规则触发",
                expected_effect="扩大 BM25 检索范围",
                priority="high",
                source="rule_engine",
            ),
        ]
    )

    mock_components["history_analyzer"].analyze = AsyncMock(return_value=[])

    mock_components["llm_diagnoser"].diagnose = AsyncMock(
        return_value=LLMDiagnosis(
            summary="Bad Case 集中在感觉统合领域",
            findings=[],
            recommendations=[
                TuningSuggestion(
                    id="llm_diag_0_rag_chunk_size",
                    param_name="rag_chunk_size",
                    current_value=None,
                    suggested_value=800,
                    action="increase",
                    reason="LLM 诊断建议",
                    expected_effect="增大分块尺寸",
                    priority="medium",
                    source="llm",
                )
            ],
        )
    )

    mock_components["conflict_detector"].detect = MagicMock(
        return_value=(
            [
                TuningSuggestion(
                    id="rule_1",
                    param_name="rag_hybrid_bm25_top_k",
                    current_value=10,
                    suggested_value=15,
                    action="increase",
                    reason="recall_optimization 规则触发",
                    expected_effect="扩大 BM25 检索范围",
                    priority="high",
                    source="rule_engine",
                ),
                TuningSuggestion(
                    id="llm_diag_0_rag_chunk_size",
                    param_name="rag_chunk_size",
                    current_value=None,
                    suggested_value=800,
                    action="increase",
                    reason="LLM 诊断建议",
                    expected_effect="增大分块尺寸",
                    priority="medium",
                    source="llm",
                ),
            ],
            0,
        )
    )

    mock_components["test_run_repo"].get_by_id = AsyncMock(
        return_value=MagicMock(
            id="test_run_2",
            overall_precision=0.75,
            overall_recall=0.60,
            overall_f1=0.66,
            overall_mrr=0.65,
            overall_ndcg=0.72,
        )
    )
    mock_components["test_run_repo"].get_results = AsyncMock(return_value=[])

    engine = TuningSuggestionEngine(
        rule_engine=mock_components["rule_engine"],
        history_analyzer=mock_components["history_analyzer"],
        llm_diagnoser=mock_components["llm_diagnoser"],
        conflict_detector=mock_components["conflict_detector"],
        test_run_repo=mock_components["test_run_repo"],
    )

    response = await engine.generate_suggestions("test_run_2")

    assert response.run_id == "test_run_2"
    assert response.total_suggestions == 2
    assert response.llm_diagnosis is not None
    assert response.llm_diagnosis.summary == "Bad Case 集中在感觉统合领域"
    assert len(response.llm_diagnosis.recommendations) == 1


@pytest.mark.asyncio
async def test_tuning_workflow_with_conflict_filtering(mock_components):
    """冲突检测过滤矛盾建议"""
    mock_components["rule_engine"].evaluate = AsyncMock(
        return_value=[
            TuningSuggestion(
                id="rule_1",
                param_name="rag_hybrid_bm25_top_k",
                current_value=10,
                suggested_value=15,
                action="increase",
                reason="recall_optimization 规则触发",
                expected_effect="扩大检索范围",
                priority="high",
                source="rule_engine",
            ),
        ]
    )

    mock_components["history_analyzer"].analyze = AsyncMock(return_value=[])
    mock_components["llm_diagnoser"].diagnose = AsyncMock(
        return_value=LLMDiagnosis(
            summary="测试",
            findings=[],
            recommendations=[
                TuningSuggestion(
                    id="llm_diag_0",
                    param_name="rag_hybrid_bm25_top_k",
                    current_value=None,
                    suggested_value=8,
                    action="decrease",
                    reason="LLM 建议降低",
                    expected_effect="减少噪声",
                    priority="low",
                    source="llm",
                )
            ],
        )
    )

    mock_components["conflict_detector"].detect = MagicMock(
        return_value=(
            [
                TuningSuggestion(
                    id="rule_1",
                    param_name="rag_hybrid_bm25_top_k",
                    current_value=10,
                    suggested_value=15,
                    action="increase",
                    reason="recall_optimization 规则触发",
                    expected_effect="扩大检索范围",
                    priority="high",
                    source="rule_engine",
                ),
            ],
            1,
        )
    )

    mock_components["test_run_repo"].get_by_id = AsyncMock(
        return_value=MagicMock(
            id="test_run_3",
            overall_precision=0.80,
            overall_recall=0.65,
            overall_f1=0.71,
            overall_mrr=0.70,
            overall_ndcg=0.75,
        )
    )
    mock_components["test_run_repo"].get_results = AsyncMock(return_value=[])

    engine = TuningSuggestionEngine(
        rule_engine=mock_components["rule_engine"],
        history_analyzer=mock_components["history_analyzer"],
        llm_diagnoser=mock_components["llm_diagnoser"],
        conflict_detector=mock_components["conflict_detector"],
        test_run_repo=mock_components["test_run_repo"],
    )

    response = await engine.generate_suggestions("test_run_3")

    assert response.conflict_filtered_count == 1
    assert response.total_suggestions == 1
    assert response.rule_engine_suggestions[0].action == "increase"
