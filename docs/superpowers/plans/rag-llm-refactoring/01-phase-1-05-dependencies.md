# Phase 1.2: 依赖安装与集成测试

> **前置文档:** [Overview](./01-phase-1-00-overview.md)
> **状态:** ✅ 基础依赖已安装，多提供商依赖待补充

### 🟡 1.5 依赖安装（✅ 基础依赖已安装，多提供商依赖待补充）
> 说明：当前项目已安装Dashscope相关依赖，OpenAI/Anthropic/Ollama等其他提供商依赖尚未安装，需要在实施时补充。

#### Task 1.5.1: 更新 pyproject.toml
**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: 添加新依赖到pyproject.toml**

> **注意**: 项目使用 PEP 621 `[project]` 格式，非 Poetry。

```toml
[project]
dependencies = [
    # 已有依赖...
    
    # OpenAI
    "langchain-openai>=0.3.0",
    "llama-index-llms-openai>=0.3.0",
    "llama-index-embeddings-openai>=0.3.0",

    # Anthropic
    "langchain-anthropic>=0.3.0",
    "llama-index-llms-anthropic>=0.4.0",

    # Ollama
    "langchain-ollama>=0.2.0",
    "llama-index-llms-ollama>=0.5.0",
    "llama-index-embeddings-ollama>=0.4.0",
]
```

- [ ] **Step 2: 验证依赖配置正确**
Run: `uv check`
Expected: All checks passed



#### Task 1.5.2: 安装并验证各提供商 SDK
**Files:**
- Test: `tests/integration/test_llm_providers.py`
- Create: `tests/conftest.py` (pytest fixtures)

- [ ] **Step 1: 安装依赖**
Run: `uv sync`
Expected: Dependencies installed successfully

- [ ] **Step 2: 创建 pytest fixtures（测试隔离）**

> **⚠️ 测试隔离**: 使用 pytest fixtures 为每个测试创建独立的工厂实例，避免修改全局状态。
> **⚠️ 异步 fixture**: 使用 `@pytest_asyncio.fixture` 支持异步 setup/teardown。

```python
# tests/conftest.py
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock
from src.core.llm.factory import LLMServiceFactory
from src.core.llm.embedding_factory import EmbeddingFactory
from src.core.llm.reranker_factory import RerankerFactory
from src.core.llm.provider_registry import ProviderRegistry

@pytest_asyncio.fixture
async def mock_config_manager():
    """创建模拟的 ConfigManager，避免测试修改全局配置"""
    manager = MagicMock()
    manager.get_full_config = MagicMock(return_value={
        "llm_report_generation": {
            "provider": "dashscope",
            "model": "qwen3.5-plus",
            "temperature": 0.7,
            "max_tokens": 2000,
            "top_p": 0.8,
            "presence_penalty": 0.0,
            "frequency_penalty": 0.0,
        },
        "llm_llm_providers": {
            "dashscope": {"api_key": "test-key"},
        },
        "embedding": {"provider": "dashscope", "model": "text-embedding-v4"},
        "rag_retrieval": {"reranker_provider": "local", "reranker_model": "BAAI/bge-reranker-v2-m3"},
    })
    return manager

@pytest_asyncio.fixture
async def llm_service_factory(mock_config_manager):
    """为每个测试创建独立的 LLMServiceFactory 实例"""
    registry = ProviderRegistry()
    factory = LLMServiceFactory(mock_config_manager, registry)
    yield factory
    # 清理
    await factory.shutdown()

@pytest_asyncio.fixture
async def embedding_factory(mock_config_manager):
    """为每个测试创建独立的 EmbeddingFactory 实例"""
    factory = EmbeddingFactory(mock_config_manager)
    yield factory
    await factory.shutdown()

@pytest_asyncio.fixture
async def reranker_factory(mock_config_manager):
    """为每个测试创建独立的 RerankerFactory 实例"""
    factory = RerankerFactory(mock_config_manager)
    yield factory
    await factory.shutdown()
```

- [ ] **Step 3: 编写提供商集成测试**

> **⚠️ 不修改全局配置**: 使用 mock ConfigManager 而非修改 `settings` 对象。

```python
import pytest
from src.core.event_bus import ConfigChangedEvent

@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.parametrize("provider", ["dashscope", "openai", "anthropic", "ollama"])
async def test_provider_connection(provider, mock_config_manager):
    from src.core.llm.factory import LLMServiceFactory
    from src.core.llm.provider_registry import ProviderRegistry
    
    # 跳过未配置的提供商
    llm_providers = mock_config_manager.get_full_config().get("llm_llm_providers", {})
    if provider not in llm_providers:
        pytest.skip(f"Provider {provider} not configured")
    
    # 更新 mock 配置
    config = mock_config_manager.get_full_config()
    config["llm_report_generation"]["provider"] = provider
    mock_config_manager.get_full_config.return_value = config
    
    # 创建工厂实例
    registry = ProviderRegistry()
    factory = LLMServiceFactory(mock_config_manager, registry)
    
    try:
        llm = await factory.create("report_generation")
        response = await llm.ainvoke("Hello, respond with 'OK'")
        assert "OK" in response.content
    finally:
        await factory.shutdown()
```

- [ ] **Step 4: 运行集成测试**
Run: `pytest tests/integration/test_llm_providers.py -v -m integration`
Expected: Configured providers pass all tests
