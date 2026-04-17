import pytest
from unittest.mock import MagicMock, AsyncMock
from src.core.validation.layers.layer5c_error_patterns import Layer5cErrorPatterns


def make_session_factory(mock_results: dict):
    """创建 session_factory mock，模拟数据库查询结果"""
    mock_session = AsyncMock()

    async def mock_execute(stmt):
        mock_result = MagicMock()
        if "bad_cases" in mock_results:
            mock_result.all.return_value = mock_results["bad_cases"]
        else:
            mock_result.all.return_value = []
        mock_result.scalars.return_value.all.return_value = []
        return mock_result

    mock_session.execute = mock_execute
    session_factory = MagicMock()
    session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    session_factory.return_value.__aexit__ = AsyncMock(return_value=None)
    return session_factory


@pytest.mark.asyncio
async def test_missing_bad_cases_skipped():
    """缺少 Bad Case 列表时跳过"""
    session_factory = make_session_factory({"bad_cases": []})
    test_run = MagicMock(id=1)
    layer = Layer5cErrorPatterns(session_factory, test_run)
    result = await layer.execute()
    assert result["status"] == "skipped"


@pytest.mark.asyncio
async def test_cross_grouping():
    """多维交叉分组正确"""
    mock_result1 = MagicMock(
        query="查询1", hit_at_1=False, hit_at_3=False, hit_at_5=False
    )
    mock_case1 = MagicMock(domain=MagicMock(value="motor"), age_months=30)
    mock_result2 = MagicMock(
        query="查询2", hit_at_1=False, hit_at_3=False, hit_at_5=False
    )
    mock_case2 = MagicMock(domain=MagicMock(value="motor"), age_months=30)
    mock_result3 = MagicMock(
        query="查询3", hit_at_1=False, hit_at_3=True, hit_at_5=False
    )
    mock_case3 = MagicMock(domain=MagicMock(value="language"), age_months=50)

    session_factory = make_session_factory(
        {
            "bad_cases": [
                (mock_result1, mock_case1),
                (mock_result2, mock_case2),
                (mock_result3, mock_case3),
            ]
        }
    )
    test_run = MagicMock(id=1)
    layer = Layer5cErrorPatterns(session_factory, test_run)
    result = await layer.execute()

    assert result["data"]["total_groups"] == 2
    assert result["data"]["total_bad_cases"] == 3
    assert result["data"]["error_groups"][0]["count"] == 2


@pytest.mark.asyncio
async def test_fix_solution_mapping():
    """修复方案规则映射正确"""
    mock_result = MagicMock(
        query="查询1", hit_at_1=False, hit_at_3=False, hit_at_5=False
    )
    mock_case = MagicMock(domain=MagicMock(value="motor"), age_months=30)
    session_factory = make_session_factory({"bad_cases": [(mock_result, mock_case)]})
    test_run = MagicMock(id=1)
    layer = Layer5cErrorPatterns(session_factory, test_run)
    result = await layer.execute()

    assert (
        result["data"]["error_groups"][0]["suggested_fix"]
        == "增加 top_k，检查关键词覆盖"
    )


@pytest.mark.asyncio
async def test_only_hit_at_5_zero_included():
    """仅 hit_at_5=0 的结果被纳入 Bad Case"""
    # 模拟数据库查询已过滤 hit_at_5=False，只返回符合条件的行
    mock_result1 = MagicMock(
        query="查询1", hit_at_1=False, hit_at_3=False, hit_at_5=False
    )
    mock_case1 = MagicMock(domain=MagicMock(value="motor"), age_months=30)
    mock_result3 = MagicMock(
        query="查询3", hit_at_1=False, hit_at_3=True, hit_at_5=False
    )
    mock_case3 = MagicMock(domain=MagicMock(value="language"), age_months=50)

    session_factory = make_session_factory(
        {
            "bad_cases": [
                (mock_result1, mock_case1),
                (mock_result3, mock_case3),
            ]
        }
    )
    test_run = MagicMock(id=1)
    layer = Layer5cErrorPatterns(session_factory, test_run)
    result = await layer.execute()

    assert result["data"]["total_bad_cases"] == 2


@pytest.mark.asyncio
async def test_groups_sorted_by_count_descending():
    """分组按数量降序排列"""
    mock_results = []
    mock_cases = []
    for i in range(5):
        mock_results.append(
            MagicMock(query=f"查询{i}", hit_at_1=False, hit_at_3=False, hit_at_5=False)
        )
        mock_cases.append(MagicMock(domain=MagicMock(value="motor"), age_months=30))
    for i in range(3):
        mock_results.append(
            MagicMock(
                query=f"查询{i + 5}", hit_at_1=False, hit_at_3=True, hit_at_5=False
            )
        )
        mock_cases.append(MagicMock(domain=MagicMock(value="language"), age_months=50))

    bad_cases = list(zip(mock_results, mock_cases))
    session_factory = make_session_factory({"bad_cases": bad_cases})
    test_run = MagicMock(id=1)
    layer = Layer5cErrorPatterns(session_factory, test_run)
    result = await layer.execute()

    assert (
        result["data"]["error_groups"][0]["count"]
        >= result["data"]["error_groups"][1]["count"]
    )


@pytest.mark.asyncio
async def test_example_queries_limited_to_3():
    """示例查询最多返回 3 条"""
    mock_results = []
    mock_cases = []
    for i in range(10):
        mock_results.append(
            MagicMock(query=f"查询{i}", hit_at_1=False, hit_at_3=False, hit_at_5=False)
        )
        mock_cases.append(MagicMock(domain=MagicMock(value="motor"), age_months=30))

    bad_cases = list(zip(mock_results, mock_cases))
    session_factory = make_session_factory({"bad_cases": bad_cases})
    test_run = MagicMock(id=1)
    layer = Layer5cErrorPatterns(session_factory, test_run)
    result = await layer.execute()

    assert len(result["data"]["error_groups"][0]["example_queries"]) == 3
