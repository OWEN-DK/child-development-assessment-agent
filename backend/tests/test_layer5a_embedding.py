import pytest
from unittest.mock import MagicMock, AsyncMock, patch
import numpy as np
from src.core.validation.layers.layer5a_embedding import Layer5aEmbeddingQuality


def make_session_factory(mock_results: dict):
    """创建 session_factory mock，模拟数据库查询结果"""
    mock_session = AsyncMock()

    async def mock_execute(stmt):
        mock_result = MagicMock()
        if "run_results" in mock_results:
            mock_result.all.return_value = mock_results["run_results"]
        else:
            mock_result.all.return_value = []
        mock_result.scalars.return_value.all.return_value = mock_results.get(
            "intent_logs", []
        )
        return mock_result

    mock_session.execute = mock_execute
    session_factory = MagicMock()
    session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    session_factory.return_value.__aexit__ = AsyncMock(return_value=None)
    return session_factory


def test_cosine_similarity_identical():
    """相同向量余弦相似度为 1"""
    session_factory = make_session_factory({})
    test_run = MagicMock(id=1)
    layer = Layer5aEmbeddingQuality(session_factory, test_run)
    a = [1.0, 2.0, 3.0]
    b = [1.0, 2.0, 3.0]
    assert abs(layer._cosine_similarity(a, b) - 1.0) < 1e-6


def test_cosine_similarity_orthogonal():
    """正交向量余弦相似度为 0"""
    session_factory = make_session_factory({})
    test_run = MagicMock(id=1)
    layer = Layer5aEmbeddingQuality(session_factory, test_run)
    a = [1.0, 0.0, 0.0]
    b = [0.0, 1.0, 0.0]
    assert abs(layer._cosine_similarity(a, b)) < 1e-6


@pytest.mark.asyncio
async def test_missing_queries_skipped():
    """缺少查询列表时跳过"""
    session_factory = make_session_factory({"run_results": []})
    test_run = MagicMock(id=1)
    layer = Layer5aEmbeddingQuality(session_factory, test_run)
    result = await layer.execute()
    assert result["status"] == "skipped"


@pytest.mark.asyncio
async def test_get_synonym_pairs_from_file():
    """从内置文件读取同义对"""
    mock_result = MagicMock(query="test")
    mock_case = MagicMock(domain=MagicMock(value="motor"))
    session_factory = make_session_factory({"run_results": [(mock_result, mock_case)]})
    test_run = MagicMock(id=1)
    layer = Layer5aEmbeddingQuality(session_factory, test_run)
    pairs = await layer._get_synonym_pairs()
    assert len(pairs) > 0
    assert "query_a" in pairs[0]


@pytest.mark.asyncio
async def test_synonym_pairs_low_similarity_warning():
    """同义对相似度低于阈值时警告"""
    mock_result1 = MagicMock(query="test1")
    mock_case1 = MagicMock(domain=MagicMock(value="motor"))
    mock_result2 = MagicMock(query="test2")
    mock_case2 = MagicMock(domain=MagicMock(value="language"))
    session_factory = make_session_factory(
        {"run_results": [(mock_result1, mock_case1), (mock_result2, mock_case2)]}
    )
    test_run = MagicMock(id=1)
    layer = Layer5aEmbeddingQuality(session_factory, test_run)

    with patch.object(
        layer, "_get_synonym_pairs", return_value=[{"query_a": "a", "query_b": "b"}]
    ):
        with patch.object(layer, "_check_synonym_pairs", return_value=0.70):
            with patch.object(layer, "_calc_silhouette_score", return_value=None):
                with patch.object(layer, "_detect_anomalies", return_value=[]):
                    result = await layer.execute()

    assert result["status"] == "completed"
    assert any("同义对相似度低" in w["message"] for w in result["data"]["warnings"])


@pytest.mark.asyncio
async def test_silhouette_score_low_warning():
    """Silhouette Score 低于阈值时警告"""
    mock_result1 = MagicMock(query="test1")
    mock_case1 = MagicMock(domain=MagicMock(value="motor"))
    mock_result2 = MagicMock(query="test2")
    mock_case2 = MagicMock(domain=MagicMock(value="language"))
    session_factory = make_session_factory(
        {"run_results": [(mock_result1, mock_case1), (mock_result2, mock_case2)]}
    )
    test_run = MagicMock(id=1)
    layer = Layer5aEmbeddingQuality(session_factory, test_run)

    with patch.object(layer, "_get_synonym_pairs", return_value=[]):
        with patch.object(layer, "_check_synonym_pairs", return_value=None):
            with patch.object(layer, "_calc_silhouette_score", return_value=0.20):
                with patch.object(layer, "_detect_anomalies", return_value=[]):
                    result = await layer.execute()

    assert result["status"] == "completed"
    assert any("区分度低" in w["message"] for w in result["data"]["warnings"])


@pytest.mark.asyncio
async def test_anomaly_detection_warning():
    """发现异常向量时警告"""
    mock_result1 = MagicMock(query="test1")
    mock_case1 = MagicMock(domain=MagicMock(value="motor"))
    mock_result2 = MagicMock(query="test2")
    mock_case2 = MagicMock(domain=MagicMock(value="language"))
    session_factory = make_session_factory(
        {"run_results": [(mock_result1, mock_case1), (mock_result2, mock_case2)]}
    )
    test_run = MagicMock(id=1)
    layer = Layer5aEmbeddingQuality(session_factory, test_run)

    anomalies = [{"query": "test1", "type": "None"}]
    with patch.object(layer, "_get_synonym_pairs", return_value=[]):
        with patch.object(layer, "_check_synonym_pairs", return_value=None):
            with patch.object(layer, "_calc_silhouette_score", return_value=None):
                with patch.object(layer, "_detect_anomalies", return_value=anomalies):
                    result = await layer.execute()

    assert result["status"] == "completed"
    assert any("异常向量" in w["message"] for w in result["data"]["warnings"])
