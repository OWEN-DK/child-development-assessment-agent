"""EmbeddingFactory 测试"""

import pytest
import asyncio
from unittest.mock import MagicMock, patch


@pytest.fixture
def mock_config_manager():
    """模拟 ConfigManager"""
    with patch("src.core.llm.embedding_factory.ConfigManager") as MockConfigManager:
        manager = MagicMock()
        manager.get_full_config.return_value = {
            "embedding": {
                "provider": "dashscope",
                "model": "text-embedding-v4",
                "batch_size": 10,
                "max_length": 1536,
            },
            "llm_providers": {
                "dashscope": {
                    "api_key": "test-api-key",
                    "base_url": None,
                }
            },
        }
        MockConfigManager.return_value = manager
        yield manager


@pytest.mark.asyncio
async def test_embedding_factory_create(mock_config_manager):
    """测试创建 Embedding 实例"""
    from src.core.llm.embedding_factory import EmbeddingFactory

    factory = EmbeddingFactory(mock_config_manager)

    # 测试创建 LangChain Embedding 实例
    embedding = await factory.create(framework="langchain")
    assert embedding is not None

    # 测试缓存命中
    embedding2 = await factory.create(framework="langchain")
    assert embedding is embedding2

    # 释放引用
    await factory.release(framework="langchain")


@pytest.mark.asyncio
async def test_embedding_factory_release(mock_config_manager):
    """测试释放引用"""
    from src.core.llm.embedding_factory import EmbeddingFactory

    factory = EmbeddingFactory(mock_config_manager)

    # 创建并释放引用
    embedding = await factory.create(framework="langchain")
    assert embedding is not None

    # 释放引用
    await factory.release(framework="langchain")

    # 验证活跃请求计数减少
    cache_key = "embedding:langchain"
    assert factory._active_requests.get(cache_key, 0) == 0


@pytest.mark.asyncio
async def test_embedding_factory_unsupported_framework(mock_config_manager):
    """测试不支持的框架抛出异常"""
    from src.core.llm.embedding_factory import EmbeddingFactory

    factory = EmbeddingFactory(mock_config_manager)

    # 测试不支持的框架
    with pytest.raises(ValueError, match="Unsupported framework"):
        await factory.create(framework="unsupported")


@pytest.mark.asyncio
async def test_embedding_factory_unsupported_provider(mock_config_manager):
    """测试不支持的提供商抛出异常"""
    from src.core.llm.embedding_factory import EmbeddingFactory

    # 修改配置为不支持的提供商
    mock_config_manager.get_full_config.return_value["embedding"] = {
        "provider": "unsupported_provider",
        "model": "test-model",
        "batch_size": 10,
        "max_length": 1536,
    }

    factory = EmbeddingFactory(mock_config_manager)

    # 测试不支持的提供商
    with pytest.raises(ValueError, match="Unsupported embedding provider"):
        await factory.create(framework="langchain")


@pytest.mark.asyncio
async def test_embedding_factory_shutdown(mock_config_manager):
    """测试优雅关闭"""
    from src.core.llm.embedding_factory import EmbeddingFactory

    factory = EmbeddingFactory(mock_config_manager)

    # 创建实例
    embedding = await factory.create(framework="langchain")
    assert embedding is not None

    # 关闭工厂
    await factory.shutdown()

    # 验证关闭后无法创建新实例
    with pytest.raises(RuntimeError, match="Factory is shutting down"):
        await factory.create(framework="langchain")
