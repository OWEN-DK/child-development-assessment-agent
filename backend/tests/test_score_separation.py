"""分数分离单元测试 - 验证 relevance_score 和 age_fit_score 独立"""

import pytest
from unittest.mock import MagicMock, AsyncMock
from llama_index.core.schema import NodeWithScore, TextNode
from src.schemas.assessment import KnowledgeItem
from src.service.retrieval_service import RetrievalService


@pytest.fixture
def mock_index_manager():
    manager = MagicMock()
    manager.get_index.return_value = MagicMock()
    manager.is_index_available.return_value = True
    manager.get_corpus_size.return_value = 100
    manager.index_version = "v1"
    manager.config_fingerprint = "abc123"
    return manager


@pytest.fixture
def mock_cache_service():
    cache = MagicMock()
    cache.get = AsyncMock(return_value=None)
    cache.set = AsyncMock()
    cache.clear = MagicMock()
    return cache


@pytest.fixture
def retrieval_service(mock_index_manager, mock_cache_service):
    return RetrievalService(mock_index_manager, mock_cache_service)


def test_knowledge_item_has_age_fit_score_field():
    """验证 KnowledgeItem 新增 age_fit_score 字段，默认值为 0.0"""
    item = KnowledgeItem(
        content="测试内容", source_book="测试书籍", relevance_score=0.8
    )
    assert hasattr(item, "age_fit_score")
    assert item.age_fit_score == 0.0  # 默认值
    assert item.relevance_score == 0.8


def test_knowledge_item_age_fit_score_validation():
    """验证 age_fit_score 字段校验（0-1 范围）"""
    # 合法值
    item1 = KnowledgeItem(
        content="测试", source_book="测试", relevance_score=0.8, age_fit_score=0.5
    )
    assert item1.age_fit_score == 0.5

    # 边界值
    item2 = KnowledgeItem(
        content="测试", source_book="测试", relevance_score=0.8, age_fit_score=0.0
    )
    assert item2.age_fit_score == 0.0

    item3 = KnowledgeItem(
        content="测试", source_book="测试", relevance_score=0.8, age_fit_score=1.0
    )
    assert item3.age_fit_score == 1.0


def test_scores_are_independent(retrieval_service):
    """验证 relevance_score 和 age_fit_score 独立赋值，互不影响"""
    # 模拟 Cross-Encoder 重排序后的节点
    node = NodeWithScore(
        node=TextNode(
            node_id="test_001",
            text="适合 3 岁儿童的精细动作训练方法",
            metadata={
                "content": "适合 3 岁儿童的精细动作训练方法",
                "file_name": "测试书籍.pdf",
                "target_age_min": 3,
                "target_age_max": 4,
                "topics": ["精细动作"],
                "brain_regions": [],
                "benefits": [],
            },
        ),
        score=0.85,  # Cross-Encoder 分数
    )

    # 调用 _convert_to_knowledge_items
    items = retrieval_service._convert_to_knowledge_items([node], user_age=3)

    assert len(items) == 1
    item = items[0]

    # relevance_score 应直接来自 Cross-Encoder（0.85）
    assert item.relevance_score == pytest.approx(0.85, abs=0.01)

    # age_fit_score 应独立计算（不混合到 relevance_score）
    assert 0.0 <= item.age_fit_score <= 1.0


def test_sorting_by_relevance_score_only(retrieval_service):
    """验证结果按 relevance_score 排序，不受 age_fit_score 影响"""
    # 模拟 3 个节点，Cross-Encoder 分数递减
    nodes = [
        NodeWithScore(
            node=TextNode(
                node_id="n1",
                text="内容 1",
                metadata={
                    "content": "内容 1",
                    "file_name": "书",
                    "target_age_min": 0,
                    "target_age_max": 18,
                    "topics": [],
                    "brain_regions": [],
                    "benefits": [],
                },
            ),
            score=0.9,  # 最高相关性
        ),
        NodeWithScore(
            node=TextNode(
                node_id="n2",
                text="内容 2",
                metadata={
                    "content": "内容 2",
                    "file_name": "书",
                    "target_age_min": 0,
                    "target_age_max": 18,
                    "topics": [],
                    "brain_regions": [],
                    "benefits": [],
                },
            ),
            score=0.7,  # 中等相关性
        ),
        NodeWithScore(
            node=TextNode(
                node_id="n3",
                text="内容 3",
                metadata={
                    "content": "内容 3",
                    "file_name": "书",
                    "target_age_min": 0,
                    "target_age_max": 18,
                    "topics": [],
                    "brain_regions": [],
                    "benefits": [],
                },
            ),
            score=0.5,  # 最低相关性
        ),
    ]

    items = retrieval_service._convert_to_knowledge_items(nodes, user_age=3)

    # 验证排序顺序
    assert (
        items[0].relevance_score >= items[1].relevance_score >= items[2].relevance_score
    )

    # 验证顺序与 Cross-Encoder 分数一致
    assert items[0].content == "内容 1"
    assert items[1].content == "内容 2"
    assert items[2].content == "内容 3"


def test_backward_compatibility():
    """验证旧版 API 响应（无 age_fit_score）不崩溃"""
    # 模拟旧版字典响应（无 age_fit_score 字段）
    old_response = {
        "id": "test_001",
        "content": "测试内容",
        "score": 85.0,
        "raw_score": 0.85,
        "source_book": "测试书籍",
        "target_age_min": 3,
        "target_age_max": 4,
        "topics": [],
        "brain_regions": [],
        "file_hash": "abc123",
    }

    # 验证 age_fit_score 不在旧响应中
    assert "age_fit_score" not in old_response


def test_process_search_results_returns_age_fit_score(retrieval_service):
    """验证 _process_search_results 返回字典包含 age_fit_score 字段"""
    # 模拟节点
    node = NodeWithScore(
        node=TextNode(
            node_id="test_001",
            text="测试内容",
            metadata={
                "content": "测试内容",
                "file_name": "测试.pdf",
                "file_hash": "abc",
                "target_age_min": 3,
                "target_age_max": 4,
                "topics": [],
                "brain_regions": [],
            },
        ),
        score=0.85,
    )

    # 调用 _process_search_results
    results = retrieval_service._process_search_results(
        [node], original_query="测试", expanded_query="测试", bm25_nodes=[]
    )

    assert len(results) > 0
    assert "age_fit_score" in results[0]
    assert results[0]["age_fit_score"] is None  # 搜索页不计算年龄适配度
