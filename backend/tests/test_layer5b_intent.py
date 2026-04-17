import pytest
from unittest.mock import MagicMock, AsyncMock
from src.core.validation.layers.layer5b_intent import Layer5bIntentAccuracy


def make_session_factory(mock_results: dict):
    """创建 session_factory mock，模拟数据库查询结果"""
    mock_session = AsyncMock()

    async def mock_execute(stmt):
        mock_result = MagicMock()
        # 返回 (RagEvalQueryIntentLog, RagEvalIntentAnnotation|None) 元组列表
        mock_result.all.return_value = mock_results.get("intent_logs", [])
        mock_result.scalars.return_value.all.return_value = []
        return mock_result

    mock_session.execute = mock_execute
    session_factory = MagicMock()
    session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    session_factory.return_value.__aexit__ = AsyncMock(return_value=None)
    return session_factory


@pytest.mark.asyncio
async def test_missing_query_analyses_skipped():
    """缺少查询分析结果时跳过"""
    session_factory = make_session_factory({"intent_logs": []})
    test_run = MagicMock(id=1)
    layer = Layer5bIntentAccuracy(session_factory, test_run)
    result = await layer.execute()
    assert result["status"] == "skipped"


@pytest.mark.asyncio
async def test_accuracy_below_threshold():
    """准确率低于 80% 时警告"""
    mock_log1 = MagicMock(
        query="test1",
        predicted_intent="factual_query",
        confidence=0.9,
        case_id="case1",
    )
    mock_annotation1 = MagicMock(intent_type="how_to")
    mock_log2 = MagicMock(
        query="test2",
        predicted_intent="how_to",
        confidence=0.9,
        case_id="case2",
    )
    mock_annotation2 = MagicMock(intent_type="how_to")
    mock_log3 = MagicMock(
        query="test3",
        predicted_intent="comparison",
        confidence=0.9,
        case_id="case3",
    )
    mock_annotation3 = MagicMock(intent_type="definition")
    session_factory = make_session_factory(
        {
            "intent_logs": [
                (mock_log1, mock_annotation1),
                (mock_log2, mock_annotation2),
                (mock_log3, mock_annotation3),
            ]
        }
    )
    test_run = MagicMock(id=1)
    layer = Layer5bIntentAccuracy(session_factory, test_run)
    result = await layer.execute()

    assert result["data"]["overall_accuracy"] == pytest.approx(1 / 3, abs=0.01)
    assert any("准确率低" in w["message"] for w in result["data"]["warnings"])


@pytest.mark.asyncio
async def test_low_confidence_ratio():
    """低置信度查询占比过高时警告"""
    mock_log1 = MagicMock(
        query="test1", predicted_intent="factual_query", confidence=0.5, case_id="case1"
    )
    mock_log2 = MagicMock(
        query="test2", predicted_intent="how_to", confidence=0.6, case_id="case2"
    )
    mock_log3 = MagicMock(
        query="test3", predicted_intent="comparison", confidence=0.9, case_id="case3"
    )
    session_factory = make_session_factory(
        {
            "intent_logs": [
                (mock_log1, None),
                (mock_log2, None),
                (mock_log3, None),
            ]
        }
    )
    test_run = MagicMock(id=1)
    layer = Layer5bIntentAccuracy(session_factory, test_run)
    result = await layer.execute()

    assert result["data"]["low_confidence_ratio"] == pytest.approx(2 / 3, abs=0.01)
    assert any("低置信度" in w["message"] for w in result["data"]["warnings"])


@pytest.mark.asyncio
async def test_accuracy_calculation_with_manual_labels():
    """手动标注数据准确率计算正确"""
    mock_log1 = MagicMock(
        query="q1",
        predicted_intent="factual_query",
        confidence=0.95,
        case_id="case1",
    )
    mock_annotation1 = MagicMock(intent_type="factual_query")
    mock_log2 = MagicMock(
        query="q2",
        predicted_intent="how_to",
        confidence=0.90,
        case_id="case2",
    )
    mock_annotation2 = MagicMock(intent_type="how_to")
    mock_log3 = MagicMock(
        query="q3",
        predicted_intent="comparison",
        confidence=0.85,
        case_id="case3",
    )
    mock_annotation3 = MagicMock(intent_type="comparison")
    mock_log4 = MagicMock(
        query="q4",
        predicted_intent="definition",
        confidence=0.70,
        case_id="case4",
    )
    session_factory = make_session_factory(
        {
            "intent_logs": [
                (mock_log1, mock_annotation1),
                (mock_log2, mock_annotation2),
                (mock_log3, mock_annotation3),
                (mock_log4, None),
            ]
        }
    )
    test_run = MagicMock(id=1)
    layer = Layer5bIntentAccuracy(session_factory, test_run)
    result = await layer.execute()

    assert result["data"]["overall_accuracy"] == 1.0
    assert len(result["data"]["warnings"]) == 0


@pytest.mark.asyncio
async def test_accuracy_by_type_breakdown():
    """按意图类型分解准确率"""
    mock_log1 = MagicMock(
        query="q1",
        predicted_intent="factual_query",
        confidence=0.9,
        case_id="case1",
    )
    mock_annotation1 = MagicMock(intent_type="factual_query")
    mock_log2 = MagicMock(
        query="q2",
        predicted_intent="factual_query",
        confidence=0.9,
        case_id="case2",
    )
    mock_annotation2 = MagicMock(intent_type="how_to")
    mock_log3 = MagicMock(
        query="q3",
        predicted_intent="how_to",
        confidence=0.9,
        case_id="case3",
    )
    mock_annotation3 = MagicMock(intent_type="how_to")
    session_factory = make_session_factory(
        {
            "intent_logs": [
                (mock_log1, mock_annotation1),
                (mock_log2, mock_annotation2),
                (mock_log3, mock_annotation3),
            ]
        }
    )
    test_run = MagicMock(id=1)
    layer = Layer5bIntentAccuracy(session_factory, test_run)
    result = await layer.execute()

    accuracy_by_type = result["data"]["accuracy_by_type"]
    assert "factual_query" in accuracy_by_type
    assert "how_to" in accuracy_by_type
