import pytest
from unittest.mock import MagicMock, AsyncMock
from src.core.validation.layers.layer4a_golden_coverage import Layer4aGoldenCoverage


def make_session_factory(test_cases=None, source_documents=None):
    """创建 session_factory 模拟，返回指定的查询结果

    test_cases: list[dict] 模拟测试用例数据
    source_documents: list[dict] 模拟源文档数据（当前层只支持单个源文档，取第一个）
    """
    test_cases = test_cases or []
    source_documents = source_documents or []

    # 使用计数器跟踪查询顺序
    query_counter = {"count": 0}

    # 模拟 session.execute() 的返回值
    async def mock_execute(stmt):
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        query_counter["count"] += 1

        # Layer 4a 的查询顺序：
        # 1. 查询 RagEvalTestCase (通过 join RagEvalTestSetCase)
        # 2. 查询 RagEvalTestSet.source_document_id
        # 3. 查询 SourceDocument
        if query_counter["count"] == 1:
            # 第一次查询：返回测试用例列表
            mock_cases = []
            for tc in test_cases:
                case_mock = MagicMock()
                case_mock.expected_document_ids = tc.get("expected_document_ids", [])
                case_mock.domain = MagicMock()
                case_mock.domain.value = tc.get("domain", "motor")
                mock_cases.append(case_mock)
            mock_scalars.all.return_value = mock_cases
            mock_result.scalars.return_value = mock_scalars
        elif query_counter["count"] == 2:
            # 第二次查询：返回 source_document_id
            mock_result.scalar_one_or_none.return_value = (
                source_documents[0].get("doc_id", "doc1") if source_documents else None
            )
        elif query_counter["count"] == 3:
            # 第三次查询：返回源文档对象
            if source_documents:
                doc_mock = MagicMock()
                doc_mock.id = source_documents[0].get("doc_id", "doc1")
                doc_mock.quality_report = source_documents[0].get("quality_report", {})
                doc_mock.chapter_structure = source_documents[0].get(
                    "chapter_structure", []
                )
                mock_result.scalar_one_or_none.return_value = doc_mock
            else:
                mock_result.scalar_one_or_none.return_value = None

        return mock_result

    # 创建 mock session
    mock_session = AsyncMock()
    mock_session.execute = mock_execute

    # 创建 session_factory 作为异步上下文管理器
    session_factory = MagicMock()
    session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    session_factory.return_value.__aexit__ = AsyncMock(return_value=None)

    return session_factory


@pytest.mark.asyncio
async def test_missing_data_skipped():
    """缺少测试用例或源文档时跳过"""
    session_factory = make_session_factory(
        test_cases=[], source_documents=[{"doc_id": "1"}]
    )
    test_run = MagicMock(test_set_id="test_set_1")
    layer = Layer4aGoldenCoverage(session_factory, test_run)
    result = await layer.execute()
    assert result["status"] == "skipped"


@pytest.mark.asyncio
async def test_low_chapter_coverage():
    """章节覆盖率低时警告"""
    # 构造 3 个章节，但测试用例只覆盖 1 个章节
    session_factory = make_session_factory(
        test_cases=[
            {"expected_document_ids": ["doc1_ch0"], "domain": "motor"},
        ],
        source_documents=[
            {
                "doc_id": "doc1",
                "quality_report": {"suggested_domains": ["motor"]},
                "chapter_structure": [
                    {"title": "ch1"},
                    {"title": "ch2"},
                    {"title": "ch3"},
                ],
            }
        ],
    )
    test_run = MagicMock(test_set_id="test_set_1")
    layer = Layer4aGoldenCoverage(session_factory, test_run)
    result = await layer.execute()

    # 1/3 的章节覆盖率
    assert result["data"]["chapter_coverage"] == pytest.approx(1 / 3, abs=0.01)
    warnings = result["data"]["warnings"]
    assert any("章节覆盖率低" in w["message"] for w in warnings)


@pytest.mark.asyncio
async def test_uncovered_domain():
    """某领域无覆盖时严重警告"""
    # 源文档包含 motor 领域
    # 但测试用例引用的文档 ID 不存在于源文档中（模拟未覆盖任何章节）
    session_factory = make_session_factory(
        test_cases=[
            {"expected_document_ids": ["nonexistent_doc"], "domain": "motor"},
        ],
        source_documents=[
            {
                "doc_id": "doc1",
                "quality_report": {"suggested_domains": ["motor"]},
                "chapter_structure": [
                    {"title": "ch1"},
                    {"title": "ch2"},
                ],
            }
        ],
    )
    test_run = MagicMock(test_set_id="test_set_1")
    layer = Layer4aGoldenCoverage(session_factory, test_run)
    result = await layer.execute()

    warnings = result["data"]["warnings"]
    # motor 领域无覆盖（因为测试用例引用的文档不存在）
    assert any("motor" in w["message"] and "无覆盖" in w["message"] for w in warnings)


@pytest.mark.asyncio
async def test_full_coverage():
    """全覆盖时无警告"""
    session_factory = make_session_factory(
        test_cases=[
            {"expected_document_ids": ["doc1_ch0"], "domain": "motor"},
            {"expected_document_ids": ["doc1_ch1"], "domain": "motor"},
        ],
        source_documents=[
            {
                "doc_id": "doc1",
                "quality_report": {"suggested_domains": ["motor"]},
                "chapter_structure": [
                    {"title": "ch1"},
                    {"title": "ch2"},
                ],
            }
        ],
    )
    test_run = MagicMock(test_set_id="test_set_1")
    layer = Layer4aGoldenCoverage(session_factory, test_run)
    result = await layer.execute()

    assert result["data"]["book_coverage"] == 1.0
    assert result["data"]["chapter_coverage"] == 1.0
    assert len(result["data"]["warnings"]) == 0
