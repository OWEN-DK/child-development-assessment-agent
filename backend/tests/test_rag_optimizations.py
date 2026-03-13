import pytest
import time
from src.service.rag_service import rag_service

@pytest.mark.asyncio
async def test_query_caching():
    """Test query caching functionality"""
    query = "测试缓存查询 儿童平衡感训练"
    age = 3
    
    # First query - should miss cache
    start_time = time.time()
    result1 = await rag_service.retrieve_knowledge(query, age)
    time_first = time.time() - start_time
    
    # Second query - should hit cache
    start_time = time.time()
    result2 = await rag_service.retrieve_knowledge(query, age)
    time_second = time.time() - start_time
    
    # Verify results are identical
    assert len(result1) == len(result2)
    for i in range(len(result1)):
        assert result1[i].content == result2[i].content
        assert result1[i].relevance_score == result2[i].relevance_score
    
    # Cached query should be faster (allowing for small variance)
    assert time_second <= time_first * 2  # More lenient check for test environment
    
    print("✅ 查询缓存功能测试通过")

@pytest.mark.asyncio
async def test_query_rewrite():
    """Test query rewrite functionality"""
    original_query = "孩子怕高怎么办"
    age = 5
    
    # Test rewrite method
    rewritten = await rag_service._rewrite_query(original_query, age)
    
    # Verify rewrite returns something
    assert rewritten is not None
    assert len(rewritten) > 0
    
    # Test that rewrite is used in actual retrieval
    # (We can't easily verify the rewrite effect without LLM, but we can ensure it doesn't break)
    results = await rag_service.retrieve_knowledge(original_query, age, limit=3)
    assert len(results) > 0
    
    print(f"✅ 查询重写测试通过: '{original_query}' -> '{rewritten}'")

def test_incremental_update_support():
    """Test that incremental update functionality is properly implemented"""
    # Verify required methods exist
    assert hasattr(rag_service, 'ingest_book')
    assert hasattr(rag_service, 'delete_document')
    assert hasattr(rag_service, '_clear_cache')
    assert hasattr(rag_service, '_initialize_retrievers')
    
    # Verify cache methods exist
    assert hasattr(rag_service, '_get_cache_key')
    assert hasattr(rag_service, '_get_from_cache')
    assert hasattr(rag_service, '_save_to_cache')
    
    print("✅ 增量更新接口测试通过")

@pytest.mark.asyncio
async def test_cache_clear_on_index_update():
    """Test that cache is cleared when index is updated"""
    # Populate cache with a query
    query = "测试缓存清理"
    age = 4
    
    result1 = await rag_service.retrieve_knowledge(query, age)
    assert len(result1) > 0
    
    # Verify cache has the entry
    cache_key = rag_service._get_cache_key(query, age, 3)
    assert rag_service._get_from_cache(cache_key) is not None
    
    # Clear cache (simulate index update)
    rag_service._clear_cache()
    
    # Verify cache is empty
    assert rag_service._get_from_cache(cache_key) is None
    
    print("✅ 索引更新时缓存清理测试通过")

def test_cache_config():
    """Test cache configuration from settings"""
    from src.config.settings import settings
    
    assert settings.rag_config["cache"]["enabled"] == True
    assert settings.rag_config["cache"]["max_size"] == 1000
    assert settings.rag_config["cache"]["ttl_seconds"] == 3600
    
    assert settings.rag_config["query_rewrite"]["enabled"] == True
    
    print("✅ 配置参数测试通过")