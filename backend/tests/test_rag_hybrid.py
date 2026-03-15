import pytest
from src.service.rag_service import rag_service


@pytest.mark.asyncio
async def test_hybrid_retrieval_basic():
    """Test basic hybrid retrieval functionality"""
    # Test with mock data since no index is built yet
    query = "平衡感训练 前庭觉 3岁儿童"
    age = 3

    # Execute retrieval
    results = await rag_service.retrieve_knowledge(query, age, limit=3)

    # Verify results (should return mock data)
    assert len(results) <= 3
    for item in results:
        assert item.target_age_min <= age <= item.target_age_max
        assert item.relevance_score >= 0
        assert item.content is not None
        assert len(item.content) > 0

    print("✅ 混合检索基础功能测试通过")


@pytest.mark.asyncio
async def test_retrieval_with_age_filter():
    """Test retrieval with age filtering"""
    query = "注意力训练"
    age = 6

    results = await rag_service.retrieve_knowledge(query, age, limit=5)

    for item in results:
        assert (
            item.target_age_min <= age <= item.target_age_max
        ), f"Item age range {item.target_age_min}-{item.target_age_max} doesn't match age {age}"

    print("✅ 年龄过滤功能测试通过")


def test_rag_service_initialization():
    """Test RagService initialization"""
    assert rag_service is not None
    # Index might be None if no documents have been ingested yet
    # Retrievers will be None if index is None

    print("✅ RAG 服务初始化测试通过")
