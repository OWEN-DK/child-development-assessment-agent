import pytest
from unittest.mock import MagicMock, AsyncMock
from datetime import datetime, timedelta, UTC
from src.core.validation.layers.layer4c_staleness import Layer4cDocumentStaleness


def make_session_factory(source_documents=None):
    """创建 session_factory 模拟，返回指定的源文档查询结果

    source_documents: list[dict] 模拟源文档数据，包含 keys: doc_id, title, file_type, created_at, chapter_structure
    """
    source_documents = source_documents or []

    # 使用计数器跟踪查询顺序
    query_counter = {"count": 0}

    async def mock_execute(stmt):
        mock_result = MagicMock()
        query_counter["count"] += 1

        # Layer 4c 的查询顺序：
        # 1. 查询 RagEvalTestSet.source_document_id
        # 2. 查询 SourceDocument
        if query_counter["count"] == 1:
            # 第一次查询：返回 source_document_id
            mock_result.scalar_one_or_none.return_value = (
                source_documents[0].get("doc_id", "doc1") if source_documents else None
            )
        elif query_counter["count"] == 2:
            # 第二次查询：返回源文档对象
            if source_documents:
                doc_data = source_documents[0]
                doc_mock = MagicMock()
                doc_mock.id = doc_data.get("doc_id", "doc1")
                doc_mock.title = doc_data.get("title", "测试文档")
                doc_mock.file_type = doc_data.get("file_type", "学术研究/实证")
                doc_mock.created_at = doc_data.get("created_at")
                doc_mock.chapter_structure = doc_data.get("chapter_structure", [])
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
async def test_missing_documents_skipped():
    """缺少源文档数据时跳过"""
    session_factory = make_session_factory(source_documents=[])
    test_run = MagicMock(test_set_id="test_set_1")
    layer = Layer4cDocumentStaleness(session_factory, test_run)
    result = await layer.execute()
    assert result["status"] == "skipped"


@pytest.mark.asyncio
async def test_stale_policy_document():
    """政策法规类 > 5 年严重警告"""
    now = datetime.now(UTC).replace(tzinfo=None)
    old_date = now - timedelta(days=365 * 6)

    session_factory = make_session_factory(
        source_documents=[
            {
                "doc_id": "doc1",
                "title": "政策文件",
                "file_type": "政策法规/指南",
                "created_at": old_date,
                "chapter_structure": [],
            },
        ]
    )
    test_run = MagicMock(test_set_id="test_set_1")
    layer = Layer4cDocumentStaleness(session_factory, test_run)
    result = await layer.execute()

    assert result["data"]["stale_count"] == 1
    warnings = result["data"]["warnings"]
    assert any("严重过期" in w["message"] for w in warnings)


@pytest.mark.asyncio
async def test_default_document_type():
    """未标注类型默认学术研究类"""
    now = datetime.now(UTC).replace(tzinfo=None)
    old_date = now - timedelta(days=365 * 15)  # 15 年 > 10 年学术研究阈值

    session_factory = make_session_factory(
        source_documents=[
            {
                "doc_id": "doc1",
                "title": "学术论文",
                "file_type": "学术研究/实证",
                "created_at": old_date,
                "chapter_structure": [],
            },
        ]
    )
    test_run = MagicMock(test_set_id="test_set_1")
    layer = Layer4cDocumentStaleness(session_factory, test_run)
    result = await layer.execute()

    assert result["data"]["stale_count"] == 1


@pytest.mark.asyncio
async def test_classic_theory_not_checked():
    """经典理论类型不检查时效性"""
    now = datetime.now(UTC).replace(tzinfo=None)
    old_date = now - timedelta(days=365 * 50)

    session_factory = make_session_factory(
        source_documents=[
            {
                "doc_id": "doc1",
                "title": "皮亚杰理论",
                "file_type": "经典理论",
                "created_at": old_date,
                "chapter_structure": [],
            },
        ]
    )
    test_run = MagicMock(test_set_id="test_set_1")
    layer = Layer4cDocumentStaleness(session_factory, test_run)
    result = await layer.execute()

    assert result["data"]["stale_count"] == 0


@pytest.mark.asyncio
async def test_fresh_documents_no_warning():
    """新鲜文档无警告"""
    now = datetime.now(UTC).replace(tzinfo=None)
    fresh_date = now - timedelta(days=30)

    session_factory = make_session_factory(
        source_documents=[
            {
                "doc_id": "doc1",
                "title": "新研究",
                "file_type": "学术研究/实证",
                "created_at": fresh_date,
                "chapter_structure": [],
            },
        ]
    )
    test_run = MagicMock(test_set_id="test_set_1")
    layer = Layer4cDocumentStaleness(session_factory, test_run)
    result = await layer.execute()

    assert result["data"]["stale_count"] == 0
    assert len(result["data"]["warnings"]) == 0
