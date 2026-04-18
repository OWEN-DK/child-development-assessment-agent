"""RerankerFactory 测试"""

import pytest
import asyncio
from unittest.mock import MagicMock, patch


@pytest.fixture
def mock_config_manager():
    """模拟 ConfigManager"""
    with patch("src.core.llm.reranker_factory.ConfigManager") as MockConfigManager:
        manager = MagicMock()
        manager.get_full_config.return_value = {
            "rag_retrieval": {
                "reranker_provider": "local",
                "reranker_model": "BAAI/bge-reranker-v2-m3",
            }
        }
        MockConfigManager.return_value = manager
        yield manager


@pytest.mark.asyncio
async def test_reranker_factory_create(mock_config_manager):
    """测试创建 Reranker 实例"""
    from src.core.llm.reranker_factory import RerankerFactory

    factory = RerankerFactory(mock_config_manager)

    # Mock _load_cross_encoder 方法
    mock_instance = MagicMock()
    with patch.object(factory, "_load_cross_encoder", return_value=mock_instance):
        # 测试创建本地 Reranker 实例
        reranker = await factory.create()
        assert reranker is not None

        # 验证缓存命中
        reranker2 = await factory.create()
        assert reranker is reranker2

        # 释放引用
        await factory.release()


@pytest.mark.asyncio
async def test_reranker_factory_release(mock_config_manager):
    """测试释放引用"""
    from src.core.llm.reranker_factory import RerankerFactory

    factory = RerankerFactory(mock_config_manager)

    # Mock _load_cross_encoder 方法
    mock_instance = MagicMock()
    with patch.object(factory, "_load_cross_encoder", return_value=mock_instance):
        # 创建并释放引用
        reranker = await factory.create()
        assert reranker is not None

        # 释放引用
        await factory.release()

        # 验证活跃请求计数减少
        cache_key = "reranker:default"
        assert factory._active_requests.get(cache_key, 0) == 0


@pytest.mark.asyncio
async def test_reranker_factory_unsupported_provider(mock_config_manager):
    """测试不支持的提供商抛出异常"""
    from src.core.llm.reranker_factory import RerankerFactory

    # 修改配置为不支持的提供商
    mock_config_manager.get_full_config.return_value["rag_retrieval"] = {
        "reranker_provider": "unsupported",
        "reranker_model": "test-model",
    }

    factory = RerankerFactory(mock_config_manager)

    # 测试不支持的提供商
    with pytest.raises(ValueError, match="Unsupported reranker provider"):
        await factory.create()


@pytest.mark.asyncio
async def test_reranker_factory_shutdown(mock_config_manager):
    """测试优雅关闭"""
    from src.core.llm.reranker_factory import RerankerFactory

    factory = RerankerFactory(mock_config_manager)

    # Mock _load_cross_encoder 方法
    mock_instance = MagicMock()
    with patch.object(factory, "_load_cross_encoder", return_value=mock_instance):
        # 创建实例
        reranker = await factory.create()
        assert reranker is not None

        # 关闭工厂
        await factory.shutdown()

        # 验证关闭后无法创建新实例
        with pytest.raises(RuntimeError, match="Factory is shutting down"):
            await factory.create()
