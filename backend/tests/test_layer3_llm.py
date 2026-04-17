import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from src.core.validation.layers.layer3_llm import Layer3LLMDiagnosis


def _make_session_factory_mock(mock_session):
    """创建支持 async with 的 session factory mock"""
    mock_cm = MagicMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_session)
    mock_cm.__aexit__ = AsyncMock(return_value=None)
    return MagicMock(return_value=mock_cm)


@pytest.mark.asyncio
async def test_bad_case_below_threshold():
    """Bad Case < 5 时跳过"""
    test_run = MagicMock(id="run-1")
    session_factory = AsyncMock()

    layer = Layer3LLMDiagnosis(session_factory, test_run)

    with patch.object(layer, "_get_bad_cases", new_callable=AsyncMock) as mock_bc:
        mock_bc.return_value = [{"query": "test"}] * 3
        result = await layer.execute()

        assert result["status"] == "skipped"
        assert "数量不足" in result["data"]["reason"]


@pytest.mark.asyncio
async def test_stratified_sampling():
    """分层抽样正确"""
    test_run = MagicMock(id="run-1")
    layer = Layer3LLMDiagnosis(AsyncMock(), test_run)

    bad_cases = [
        {"domain": "motor", "age_group": "2-3"},
        {"domain": "motor", "age_group": "2-3"},
        {"domain": "motor", "age_group": "2-3"},
        {"domain": "motor", "age_group": "2-3"},
        {"domain": "language", "age_group": "4-5"},
        {"domain": "language", "age_group": "4-5"},
        {"domain": "language", "age_group": "4-5"},
    ]

    result = layer._stratified_sample(bad_cases, 6)
    assert len(result) <= 6


@pytest.mark.asyncio
async def test_stratified_sampling_preserves_distribution():
    """分层抽样保留分布特征"""
    test_run = MagicMock(id="run-1")
    layer = Layer3LLMDiagnosis(AsyncMock(), test_run)

    bad_cases = [
        {"domain": "motor", "age_group": "2-3", "query": f"q{i}"} for i in range(20)
    ] + [
        {"domain": "language", "age_group": "4-5", "query": f"q{i}"}
        for i in range(20, 40)
    ]

    result = layer._stratified_sample(bad_cases, 10)

    domains = {bc["domain"] for bc in result}
    assert "motor" in domains
    assert "language" in domains


@pytest.mark.asyncio
async def test_parse_llm_response():
    """解析 LLM 响应正确"""
    test_run = MagicMock(id="run-1")
    layer = Layer3LLMDiagnosis(AsyncMock(), test_run)

    response = '[{"query": "test", "failure_type": "未召回", "root_cause": "关键词缺失", "confidence": 0.8, "suggestion": "增加同义词", "priority": "HIGH"}]'
    result = layer._parse_llm_response(response)

    assert len(result) == 1
    assert result[0]["failure_type"] == "未召回"


@pytest.mark.asyncio
async def test_parse_llm_response_broken_json():
    """解析损坏的 JSON 时使用 json-repair"""
    test_run = MagicMock(id="run-1")
    layer = Layer3LLMDiagnosis(AsyncMock(), test_run)

    response = '[{"query": "test", "failure_type": "未召回"}'
    result = layer._parse_llm_response(response)

    assert len(result) >= 1
    assert result[0]["failure_type"] == "未召回"


@pytest.mark.asyncio
async def test_parse_llm_response_invalid():
    """解析完全无效的响应返回空列表"""
    test_run = MagicMock(id="run-1")
    layer = Layer3LLMDiagnosis(AsyncMock(), test_run)

    response = "这是一段完全无效的文本，没有任何 JSON 结构"
    result = layer._parse_llm_response(response)

    assert isinstance(result, list)


@pytest.mark.asyncio
async def test_summarize():
    """汇总统计正确"""
    test_run = MagicMock(id="run-1")
    layer = Layer3LLMDiagnosis(AsyncMock(), test_run)

    diagnosis = [
        {"failure_type": "未召回", "root_cause": "关键词缺失"},
        {"failure_type": "未召回", "root_cause": "关键词缺失"},
        {"failure_type": "排序倒置", "root_cause": "Embedding 质量问题"},
    ]

    result = layer._summarize(diagnosis)

    assert result["data"]["summary"]["most_common_failure_type"] == "未召回"
    assert result["data"]["summary"]["most_common_root_cause"] == "关键词缺失"
    assert result["data"]["summary"]["total_analyzed"] == 3


@pytest.mark.asyncio
async def test_summarize_empty():
    """空诊断列表汇总"""
    test_run = MagicMock(id="run-1")
    layer = Layer3LLMDiagnosis(AsyncMock(), test_run)

    result = layer._summarize([])

    assert result["data"]["summary"]["most_common_failure_type"] is None
    assert result["data"]["summary"]["most_common_root_cause"] is None
    assert result["data"]["summary"]["total_analyzed"] == 0


@pytest.mark.asyncio
async def test_llm_degradation():
    """LLM 不可用时降级"""
    test_run = MagicMock(id="run-1", config_snapshot={})
    session_factory = AsyncMock()

    layer = Layer3LLMDiagnosis(session_factory, test_run)

    with patch.object(layer, "_get_bad_cases", new_callable=AsyncMock) as mock_bc:
        mock_bc.return_value = [{"query": "test"}] * 10
        with patch.object(
            layer, "_call_llm_with_retry", new_callable=AsyncMock
        ) as mock_llm:
            mock_llm.side_effect = Exception("LLM 服务不可用")

            result = await layer.execute()

            assert result["status"] == "degraded"
            assert "LLM 服务不可用" in result["data"]["reason"]


@pytest.mark.asyncio
async def test_get_bad_cases():
    """获取 Bad Case 列表正确"""
    mock_session = AsyncMock()
    test_run = MagicMock(id="run-1")
    session_factory = _make_session_factory_mock(mock_session)

    mock_result = MagicMock()
    mock_run_result = MagicMock()
    mock_run_result.query = "测试查询"
    mock_run_result.hit_at_1 = False
    mock_run_result.hit_at_3 = False
    mock_run_result.hit_at_5 = False
    mock_run_result.matched_doc_ids = []
    mock_run_result.matched_doc_scores = []
    mock_run_result.case_id = "case-1"
    mock_result.scalars.return_value.all.return_value = [mock_run_result]

    mock_tc_result = MagicMock()
    mock_tc = MagicMock()
    mock_tc.expected_document_ids = ["doc-1", "doc-2"]
    mock_tc.domain.value = "language"
    mock_tc.age_months = 36
    mock_tc_result.scalar_one_or_none.return_value = mock_tc

    mock_session.execute.side_effect = [mock_result, mock_tc_result]

    layer = Layer3LLMDiagnosis(session_factory, test_run)
    bad_cases = await layer._get_bad_cases()

    assert len(bad_cases) == 1
    assert bad_cases[0]["query"] == "测试查询"
    assert bad_cases[0]["expected_docs"] == ["doc-1", "doc-2"]
    assert bad_cases[0]["domain"] == "language"
    assert bad_cases[0]["age_months"] == 36


@pytest.mark.asyncio
async def test_get_bad_cases_no_results():
    """无 Bad Case 时返回空列表"""
    mock_session = AsyncMock()
    test_run = MagicMock(id="run-1")
    session_factory = _make_session_factory_mock(mock_session)

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_session.execute.return_value = mock_result

    layer = Layer3LLMDiagnosis(session_factory, test_run)
    bad_cases = await layer._get_bad_cases()

    assert bad_cases == []


@pytest.mark.asyncio
async def test_execute_full_flow():
    """完整流程执行"""
    test_run = MagicMock(id="run-1", config_snapshot={"bm25_top_k": 10})
    session_factory = AsyncMock()

    bad_cases = [
        {
            "query": f"测试查询 {i}",
            "expected_docs": ["doc-1"],
            "actual_docs": [],
            "matched_scores": [],
            "hit_at_1": False,
            "hit_at_3": False,
            "hit_at_5": False,
            "domain": "language",
            "age_months": 36,
        }
        for i in range(10)
    ]

    layer = Layer3LLMDiagnosis(session_factory, test_run)

    with patch.object(layer, "_get_bad_cases", new_callable=AsyncMock) as mock_bc:
        mock_bc.return_value = bad_cases
        with patch.object(
            layer, "_call_llm_with_retry", new_callable=AsyncMock
        ) as mock_llm:
            mock_llm.return_value = '[{"query": "测试查询 0", "failure_type": "未召回", "root_cause": "关键词缺失", "confidence": 0.9, "suggestion": "增加同义词覆盖", "priority": "HIGH"}]'

            result = await layer.execute()

            assert result["status"] == "completed"
            assert "diagnosis" in result["data"]
            assert "summary" in result["data"]
            assert result["data"]["summary"]["total_analyzed"] == 1
