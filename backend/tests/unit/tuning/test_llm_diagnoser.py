"""LLM 诊断器测试:验证 Bad Case 聚合和 LLM 输出解析"""

import pytest
from unittest.mock import MagicMock, AsyncMock


@pytest.mark.asyncio
async def test_diagnose_returns_none_when_bad_cases_less_than_3():
    """Bad Case < 3 时不应触发 LLM 调用"""
    from src.core.tuning.llm_diagnoser import LLMDiagnoser

    mock_test_run_result_repo = AsyncMock()
    mock_test_run_result_repo.get_failed_results = AsyncMock(
        return_value=[MagicMock(test_case_id="tc_1"), MagicMock(test_case_id="tc_2")]
    )

    diagnoser = LLMDiagnoser(mock_test_run_result_repo, None, None, None)
    result = await diagnoser.diagnose("test_run_id")

    assert result is None


@pytest.mark.asyncio
async def test_aggregate_bad_cases_computes_domain_distribution():
    """Bad Case 聚合应正确计算领域分布"""
    from src.core.tuning.llm_diagnoser import LLMDiagnoser

    bad_cases = [
        {"domain": "sensory_integration", "age": 2.0},
        {"domain": "sensory_integration", "age": 3.0},
        {"domain": "gross_motor", "age": 5.0},
    ]

    diagnoser = LLMDiagnoser(None, None, None, None)
    stats = diagnoser._aggregate_bad_cases(bad_cases)

    assert stats["domain_distribution"]["sensory_integration"] == 2
    assert stats["domain_distribution"]["gross_motor"] == 1


@pytest.mark.asyncio
async def test_parse_llm_output_with_json_repair():
    """应正确解析 LLM 输出"""
    from src.core.tuning.llm_diagnoser import LLMDiagnoser

    raw_output = """
    {
      "summary": "测试诊断总结",
      "findings": [
        {"category": "domain_concentration", "description": "测试发现", "confidence": 0.85}
      ],
      "recommendations": [
        {
          "param": "rag_hybrid_bm25_top_k",
          "action": "increase",
          "suggested_value": 15,
          "expected_effect": "提升召回率",
          "priority": "high"
        }
      ]
    }
    """

    diagnoser = LLMDiagnoser(None, None, None, None)
    result = diagnoser._parse_llm_output(raw_output)

    assert result is not None
    assert result.summary == "测试诊断总结"
    assert len(result.findings) == 1
    assert len(result.recommendations) == 1
    assert result.recommendations[0].param_name == "rag_hybrid_bm25_top_k"
