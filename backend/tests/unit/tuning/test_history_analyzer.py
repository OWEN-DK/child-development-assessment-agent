"""历史对比分析器测试:验证配置快照对比和指标变化提取"""

import pytest
from unittest.mock import MagicMock, AsyncMock


@pytest.mark.asyncio
async def test_diff_configs_extracts_changed_params():
    """配置快照对比应正确提取变更参数"""
    from src.core.tuning.history_analyzer import HistoryAnalyzer

    old_snapshot = {"rag_hybrid_bm25_top_k": 10, "rag_reranker_final_k": 5}
    new_snapshot = {"rag_hybrid_bm25_top_k": 15, "rag_reranker_final_k": 5}

    analyzer = HistoryAnalyzer(None, None)
    diff = analyzer._diff_configs(old_snapshot, new_snapshot)

    assert "rag_hybrid_bm25_top_k" in diff
    assert diff["rag_hybrid_bm25_top_k"]["from"] == 10
    assert diff["rag_hybrid_bm25_top_k"]["to"] == 15
    assert "rag_reranker_final_k" not in diff


@pytest.mark.asyncio
async def test_analyze_returns_empty_when_less_than_2_history_runs():
    """历史运行 < 2 次时应返回空列表"""
    from src.core.tuning.history_analyzer import HistoryAnalyzer

    mock_run = MagicMock(id="run_1")
    mock_test_run_repo = AsyncMock()
    mock_test_run_repo.get_completed_runs = AsyncMock(return_value=[mock_run])

    analyzer = HistoryAnalyzer(mock_test_run_repo, None)
    references = await analyzer.analyze(
        current_metrics={"overall_recall": 0.65},
        current_run_id="current_run",
    )

    assert len(references) == 0


@pytest.mark.asyncio
async def test_analyze_extracts_metric_changes_between_runs():
    """应正确提取两次历史运行之间的指标变化"""
    from src.core.tuning.history_analyzer import HistoryAnalyzer

    mock_run_1 = MagicMock(
        id="run_1",
        config_version_id="v2",
        previous_config_version_id="v1",
        overall_recall=0.78,
        overall_precision=0.81,
        overall_f1=0.70,
        overall_mrr=0.68,
        overall_ndcg=0.75,
        created_at=MagicMock(strftime=MagicMock(return_value="2026-04-10")),
    )
    mock_run_2 = MagicMock(
        id="run_2",
        config_version_id="v1",
        previous_config_version_id=None,
        overall_recall=0.62,
        overall_precision=0.85,
        overall_f1=0.68,
        overall_mrr=0.65,
        overall_ndcg=0.72,
        created_at=MagicMock(strftime=MagicMock(return_value="2026-04-05")),
    )

    mock_test_run_repo = AsyncMock()
    mock_test_run_repo.get_completed_runs = AsyncMock(
        return_value=[mock_run_1, mock_run_2]
    )

    mock_config_manager = AsyncMock()
    mock_config_manager.get_version_config = AsyncMock(
        side_effect=lambda vid: {
            "v1": {"rag_hybrid_bm25_top_k": 10},
            "v2": {"rag_hybrid_bm25_top_k": 15},
        }.get(vid)
    )

    analyzer = HistoryAnalyzer(mock_test_run_repo, mock_config_manager)
    references = await analyzer.analyze(
        current_metrics={"overall_recall": 0.65},
        current_run_id="current_run",
    )

    assert len(references) >= 2
    # references[1] 是 run_2 → run_1 的对比
    assert "overall_recall" in references[1].metric_changes
    assert references[1].metric_changes["overall_recall"]["from"] == 0.62
    assert references[1].metric_changes["overall_recall"]["to"] == 0.78


@pytest.mark.asyncio
async def test_find_similar_runs_matches_recall_issue():
    """召回率不足的历史运行应被匹配"""
    from src.core.tuning.history_analyzer import HistoryAnalyzer

    current_metrics = {"overall_recall": 0.60, "overall_precision": 0.85}
    history_runs = [
        MagicMock(
            overall_recall=0.62,
            overall_precision=0.83,
            overall_mrr=0.7,
            overall_ndcg=0.8,
        ),
        MagicMock(
            overall_recall=0.90,
            overall_precision=0.60,
            overall_mrr=0.7,
            overall_ndcg=0.8,
        ),
    ]

    analyzer = HistoryAnalyzer(None, None)
    similar = analyzer._find_similar_runs(current_metrics, history_runs)

    assert len(similar) == 1
    assert similar[0].overall_recall < 0.7
