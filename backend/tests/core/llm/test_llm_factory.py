"""LLMServiceFactory 测试"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.fixture
def mock_config_manager():
    """模拟 ConfigManager"""
    with patch("src.core.llm.factory.ConfigManager") as MockConfigManager:
        manager = MagicMock()
        manager.get_full_config.return_value = {
            "llm_report_generation": {
                "provider": "dashscope",
                "model": "qwen-plus",
                "temperature": 0.7,
                "max_tokens": 2000,
                "top_p": 0.8,
                "presence_penalty": 0.0,
                "frequency_penalty": 0.0,
            },
            "llm_validation": {
                "provider": "dashscope",
                "model": "qwen-turbo",
                "temperature": 0.5,
                "max_tokens": 1000,
                "top_p": 0.9,
                "presence_penalty": 0.0,
                "frequency_penalty": 0.0,
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


@pytest.fixture
def mock_provider_registry():
    """模拟 ProviderRegistry"""
    with patch("src.core.llm.factory.ProviderRegistry") as MockRegistry:
        registry = MagicMock()
        # 模拟 DashScope LangChain 适配器
        mock_cls = MagicMock()
        mock_instance = MagicMock()
        mock_cls.return_value = mock_instance
        registry.get.return_value = mock_cls
        MockRegistry.return_value = registry
        yield registry


@pytest.mark.asyncio
async def test_llm_service_factory_create(mock_config_manager, mock_provider_registry):
    """测试创建 LLM 实例"""
    from src.core.llm.factory import LLMServiceFactory

    factory = LLMServiceFactory(mock_config_manager, mock_provider_registry)

    # 测试创建报告生成场景的 LLM 服务
    llm = await factory.create("report_generation", framework="langchain")
    assert llm is not None

    # 验证 ProviderRegistry 被正确调用
    mock_provider_registry.get.assert_called_with("dashscope", "langchain")

    # 测试缓存命中（同一场景返回同一实例）
    llm2 = await factory.create("report_generation", framework="langchain")
    assert llm is llm2


@pytest.mark.asyncio
async def test_llm_service_factory_release(mock_config_manager, mock_provider_registry):
    """测试释放引用"""
    from src.core.llm.factory import LLMServiceFactory

    factory = LLMServiceFactory(mock_config_manager, mock_provider_registry)

    # 创建并释放引用
    llm = await factory.create("report_generation", framework="langchain")
    assert llm is not None

    # 释放引用
    await factory.release("report_generation", framework="langchain")

    # 验证活跃请求计数减少
    cache_key = "report_generation:langchain"
    assert factory._active_requests.get(cache_key, 0) == 0


@pytest.mark.asyncio
async def test_llm_service_factory_unknown_scene(
    mock_config_manager, mock_provider_registry
):
    """测试未知场景抛出异常"""
    from src.core.llm.factory import LLMServiceFactory

    factory = LLMServiceFactory(mock_config_manager, mock_provider_registry)

    # 测试未知场景
    with pytest.raises(ValueError, match="Unknown LLM scene"):
        await factory.create("unknown_scene", framework="langchain")


@pytest.mark.asyncio
async def test_llm_service_factory_unknown_provider(
    mock_config_manager, mock_provider_registry
):
    """测试未知提供商抛出异常"""
    from src.core.llm.factory import LLMServiceFactory
    from src.config.modules.models.llm import LLMSceneConfig

    # 修改配置为未知提供商
    mock_config_manager.get_full_config.return_value["llm_report_generation"] = {
        "provider": "unknown_provider",
        "model": "test-model",
        "temperature": 0.7,
        "max_tokens": 2000,
        "top_p": 0.8,
        "presence_penalty": 0.0,
        "frequency_penalty": 0.0,
    }

    # 模拟 ProviderRegistry 返回 None
    mock_provider_registry.get.return_value = None

    factory = LLMServiceFactory(mock_config_manager, mock_provider_registry)

    # 测试未知提供商
    with pytest.raises(ValueError, match="Unknown LLM provider"):
        await factory.create("report_generation", framework="langchain")


@pytest.mark.asyncio
async def test_llm_service_factory_shutdown(
    mock_config_manager, mock_provider_registry
):
    """测试优雅关闭"""
    from src.core.llm.factory import LLMServiceFactory

    factory = LLMServiceFactory(mock_config_manager, mock_provider_registry)

    # 创建实例
    llm = await factory.create("report_generation", framework="langchain")
    assert llm is not None

    # 关闭工厂
    await factory.shutdown()

    # 验证关闭后无法创建新实例
    with pytest.raises(RuntimeError, match="Factory is shutting down"):
        await factory.create("report_generation", framework="langchain")
