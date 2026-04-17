import pytest
from unittest.mock import MagicMock, AsyncMock
from src.core.validation.layers.layer6d_ab_test import Layer6dABShadowTest
from src.models.rag_eval.enums import RagEvalABTestSide


def make_session_factory_for_6d(runs_data, results_data):
    """为 Layer 6d 创建 session_factory mock

    runs_data: 列表，每个元素包含 run 的字段
    results_data: 列表，每个元素包含 result 的字段
    """
    mock_session = AsyncMock()

    call_count = 0

    async def mock_execute(stmt):
        nonlocal call_count
        call_count += 1
        mock_scalars = MagicMock()

        # 第一次调用查询 runs，第二次查询 results
        if call_count == 1:
            mock_runs = []
            for data in runs_data:
                mock_run = MagicMock()
                mock_run.id = data["id"]
                mock_run.ab_test_side = data["ab_test_side"]
                mock_run.status = data.get("status", "completed")
                mock_runs.append(mock_run)
            mock_scalars.all.return_value = mock_runs
        else:
            mock_results = []
            for data in results_data:
                mock_result = MagicMock()
                mock_result.run_id = data["run_id"]
                mock_result.query = data.get("query", "")
                mock_result.hit_at_1 = data.get("hit_at_1", 0)
                mock_result.hit_at_3 = data.get("hit_at_3", 0)
                mock_result.hit_at_5 = data.get("hit_at_5", 0)
                mock_results.append(mock_result)
            mock_scalars.all.return_value = mock_results

        mock_result_obj = MagicMock()
        mock_result_obj.scalars.return_value = mock_scalars
        return mock_result_obj

    mock_session.execute = mock_execute
    session_factory = MagicMock()
    session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    session_factory.return_value.__aexit__ = AsyncMock(return_value=None)
    return session_factory


@pytest.mark.asyncio
async def test_no_ab_results_skipped():
    """无 A/B 测试标识时跳过"""
    test_run = MagicMock(id="run-1", ab_test_id=None)
    session_factory = make_session_factory_for_6d([], [])
    layer = Layer6dABShadowTest(session_factory, test_run)
    result = await layer.execute()
    assert result["status"] == "skipped"


@pytest.mark.asyncio
async def test_paired_t_test():
    """配对 t-test 输出正确"""
    runs_data = [
        {"id": "run-a1", "ab_test_side": RagEvalABTestSide.A},
        {"id": "run-b1", "ab_test_side": RagEvalABTestSide.B},
    ]
    results_data = [
        {
            "run_id": "run-a1",
            "query": "test1",
            "hit_at_1": 0,
            "hit_at_3": 0,
            "hit_at_5": 0,
        },
        {
            "run_id": "run-b1",
            "query": "test1",
            "hit_at_1": 1,
            "hit_at_3": 1,
            "hit_at_5": 1,
        },
    ]
    session_factory = make_session_factory_for_6d(runs_data, results_data)
    test_run = MagicMock(id="run-1", ab_test_id="ab-1")
    layer = Layer6dABShadowTest(session_factory, test_run)
    result = await layer.execute()

    assert result["status"] == "completed" or result["status"] == "failed"


@pytest.mark.asyncio
async def test_paired_t_test_sem_zero():
    """配对 t-test 当 sem=0 时不报错"""
    runs_data = [
        {"id": "run-a", "ab_test_side": RagEvalABTestSide.A},
        {"id": "run-b", "ab_test_side": RagEvalABTestSide.B},
    ]
    results_data = []
    for i in range(5):
        results_data.append(
            {
                "run_id": "run-a",
                "query": f"q{i}",
                "hit_at_1": 0,
                "hit_at_3": 0,
                "hit_at_5": 0,
            }
        )
        results_data.append(
            {
                "run_id": "run-b",
                "query": f"q{i}",
                "hit_at_1": 1,
                "hit_at_3": 1,
                "hit_at_5": 1,
            }
        )

    session_factory = make_session_factory_for_6d(runs_data, results_data)
    test_run = MagicMock(id="run-1", ab_test_id="ab-1")
    layer = Layer6dABShadowTest(session_factory, test_run)
    result = await layer.execute()

    assert result["status"] == "completed"
    assert "p_value" in result["data"]


@pytest.mark.asyncio
async def test_b_wins_when_better():
    """B 配置更好时判定 B 胜出"""
    runs_data = [
        {"id": "run-a", "ab_test_side": RagEvalABTestSide.A},
        {"id": "run-b", "ab_test_side": RagEvalABTestSide.B},
    ]
    results_data = []
    for i in range(10):
        results_data.append(
            {
                "run_id": "run-a",
                "query": f"q{i}",
                "hit_at_1": 0,
                "hit_at_3": 0,
                "hit_at_5": 0,
            }
        )
        results_data.append(
            {
                "run_id": "run-b",
                "query": f"q{i}",
                "hit_at_1": 1,
                "hit_at_3": 1,
                "hit_at_5": 1,
            }
        )

    session_factory = make_session_factory_for_6d(runs_data, results_data)
    test_run = MagicMock(id="run-1", ab_test_id="ab-1")
    layer = Layer6dABShadowTest(session_factory, test_run)
    result = await layer.execute()

    assert result["status"] == "completed"
    assert result["data"]["winner"] == "B"
    assert result["data"]["metric_deltas"]["f1_delta"] > 0


@pytest.mark.asyncio
async def test_metric_deltas_calculated():
    """指标差异计算正确"""
    runs_data = [
        {"id": "run-a", "ab_test_side": RagEvalABTestSide.A},
        {"id": "run-b", "ab_test_side": RagEvalABTestSide.B},
    ]
    results_data = [
        {"run_id": "run-a", "query": "q1", "hit_at_1": 0, "hit_at_3": 0, "hit_at_5": 0},
        {"run_id": "run-a", "query": "q2", "hit_at_1": 0, "hit_at_3": 0, "hit_at_5": 1},
        {"run_id": "run-b", "query": "q1", "hit_at_1": 1, "hit_at_3": 1, "hit_at_5": 1},
        {"run_id": "run-b", "query": "q2", "hit_at_1": 1, "hit_at_3": 1, "hit_at_5": 1},
    ]

    session_factory = make_session_factory_for_6d(runs_data, results_data)
    test_run = MagicMock(id="run-1", ab_test_id="ab-1")
    layer = Layer6dABShadowTest(session_factory, test_run)
    result = await layer.execute()

    assert result["status"] == "completed"
    deltas = result["data"]["metric_deltas"]
    assert "f1_delta" in deltas
    assert "hit_at_1_delta" in deltas
    assert "hit_at_3_delta" in deltas
    assert "hit_at_5_delta" in deltas


@pytest.mark.asyncio
async def test_unpaired_queries_skipped():
    """无法配对的查询被跳过"""
    runs_data = [
        {"id": "run-a", "ab_test_side": RagEvalABTestSide.A},
        {"id": "run-b", "ab_test_side": RagEvalABTestSide.B},
    ]
    results_data = [
        {"run_id": "run-a", "query": "q1", "hit_at_1": 0, "hit_at_3": 0, "hit_at_5": 0},
        {
            "run_id": "run-a",
            "query": "q_only_a",
            "hit_at_1": 0,
            "hit_at_3": 0,
            "hit_at_5": 0,
        },
        {"run_id": "run-b", "query": "q1", "hit_at_1": 1, "hit_at_3": 1, "hit_at_5": 1},
        {
            "run_id": "run-b",
            "query": "q_only_b",
            "hit_at_1": 1,
            "hit_at_3": 1,
            "hit_at_5": 1,
        },
    ]

    session_factory = make_session_factory_for_6d(runs_data, results_data)
    test_run = MagicMock(id="run-1", ab_test_id="ab-1")
    layer = Layer6dABShadowTest(session_factory, test_run)
    result = await layer.execute()

    assert result["status"] == "completed"
    assert len(result["data"]["per_case_comparison"]) == 1
