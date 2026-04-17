# Phase 1.1: 工厂类重构

> **前置文档:** [Overview](./01-phase-1-00-overview.md) | [配置层改造](./01-phase-1-01-config-layer.md)
> **状态:** ⚠️ 部分实现（当前仅支持单提供商）

### 🟠 1.2 工厂类重构（⚠️ 部分实现）
> 说明：当前已实现基础`LLMServiceFactory`，支持按场景创建LangChain/LlamaIndex实例，但尚未实现多提供商注册、动态选择、热更新、延迟销毁等规划中的高级功能。

#### Task 1.2.1: 创建 Provider Registry
**Files:**
- Create: `src/core/llm/provider_registry.py`
- Test: `tests/core/llm/test_provider_registry.py`

- [ ] **Step 1: 编写测试用例**
```python
import pytest
from src.core.di_container import injector

@pytest.mark.asyncio
async def test_provider_registry():
    from src.core.llm.provider_registry import ProviderRegistry
    
    # 通过 DI 容器获取实例
    provider_registry = injector.get(ProviderRegistry)
    
    # 验证DashScope LangChain适配器已注册
    dashscope_langchain_cls = provider_registry.get("dashscope", "langchain")
    assert dashscope_langchain_cls is not None
    
    # 验证Ollama LlamaIndex适配器已注册
    ollama_llamaindex_cls = provider_registry.get("ollama", "llamaindex")
    assert ollama_llamaindex_cls is not None
    
    # 验证未知提供商返回None
    assert provider_registry.get("unknown", "langchain") is None
```

- [ ] **Step 2: 运行测试验证失败**
Run: `pytest tests/core/llm/test_provider_registry.py::test_provider_registry -v`
Expected: FAIL with "No module named 'src.core.llm.provider_registry'"

- [ ] **Step 3: 实现Provider Registry**

> **⚠️ DI 容器管理**: ProviderRegistry 使用 `@singleton` 装饰器，通过 DI 容器获取实例，便于单元测试 mock。
> **⚠️ 按提供商隔离 ImportError**: 每个提供商独立 try/except，避免单个依赖缺失导致全部注册失败。
> **⚠️ 大小写归一化**: 注册和查询时统一使用 `.lower()` 避免大小写不匹配。

```python
from typing import Dict, Tuple, Type, Optional
from injector import singleton
from langchain_core.language_models import BaseChatModel
from llama_index.core.llms import LLM as LlamaIndexLLM

@singleton
class ProviderRegistry:
    def __init__(self):
        self._registry: Dict[Tuple[str, str], Type] = {}
        self._register_default_providers()
    
    def register(self, provider: str, framework: str, cls: Type):
        """注册LLM类到注册表"""
        self._registry[(provider.lower(), framework.lower())] = cls
    
    def get(self, provider: str, framework: str) -> Optional[Type]:
        """根据提供商和框架获取LLM类（自动归一化为小写）"""
        return self._registry.get((provider.lower(), framework.lower()))
    
    def _register_default_providers(self):
        """注册默认提供商适配器（按提供商隔离 ImportError）"""
        # DashScope
        try:
            from langchain_community.chat_models import ChatTongyi
            self.register("dashscope", "langchain", ChatTongyi)
        except ImportError:
            pass
        
        try:
            from llama_index.llms.dashscope import DashScope
            self.register("dashscope", "llamaindex", DashScope)
        except ImportError:
            pass
        
        # OpenAI
        try:
            from langchain_openai import ChatOpenAI
            self.register("openai", "langchain", ChatOpenAI)
        except ImportError:
            pass
            
        try:
            from llama_index.llms.openai import OpenAI
            self.register("openai", "llamaindex", OpenAI)
        except ImportError:
            pass
        
        # Anthropic
        try:
            from langchain_anthropic import ChatAnthropic
            self.register("anthropic", "langchain", ChatAnthropic)
        except ImportError:
            pass
            
        try:
            from llama_index.llms.anthropic import Anthropic
            self.register("anthropic", "llamaindex", Anthropic)
        except ImportError:
            pass
        
        # Ollama
        try:
            from langchain_ollama import ChatOllama
            self.register("ollama", "langchain", ChatOllama)
        except ImportError:
            pass
            
        try:
            from llama_index.llms.ollama import Ollama
            self.register("ollama", "llamaindex", Ollama)
        except ImportError:
            pass
        
        # DeepSeek (通过 OpenAI 兼容接口，需配合 base_url 覆盖)
        try:
            from langchain_openai import ChatOpenAI
            self.register("deepseek", "langchain", ChatOpenAI)
        except ImportError:
            pass
            
        try:
            from llama_index.llms.openai import OpenAI
            self.register("deepseek", "llamaindex", OpenAI)
        except ImportError:
            pass

# 通过 DI 容器获取实例
# provider_registry = injector.get(ProviderRegistry)
```

- [ ] **Step 4: 运行测试验证通过**
Run: `pytest tests/core/llm/test_provider_registry.py::test_provider_registry -v`
Expected: PASS



#### Task 1.2.2: 重构 LLMServiceFactory
**Files:**
- Modify: `src/core/llm/factory.py`
- Test: `tests/core/llm/test_llm_factory.py`

- [ ] **Step 1: 编写测试用例**

> **⚠️ 使用 pytest fixture**: 通过 `conftest.py` 注入工厂实例，而非引用未定义的模块级变量。

```python
import pytest

@pytest.mark.asyncio
async def test_llm_service_factory_create(llm_service_factory):
    from src.config.modules.models.llm import LLMSceneConfig
    
    # 测试创建报告生成场景的LLM服务
    llm = await llm_service_factory.create("report_generation", framework="langchain")
    assert llm is not None
    
    # 验证模型名称（使用 qwen3.5-plus）
    model_attr = getattr(llm, "model_name", None) or getattr(llm, "model", None)
    assert model_attr == "qwen3.5-plus"
    
    # 测试再次创建报告生成场景的LLM服务
    llm2 = await llm_service_factory.create("report_generation", framework="langchain")
    assert llm2 is not None
    
    # 验证缓存命中（同一场景返回同一实例）
    assert llm is llm2
    
    # 释放引用
    await llm_service_factory.release("report_generation")
    await llm_service_factory.release("report_generation")
```

- [ ] **Step 2: 运行测试验证失败**
Run: `pytest tests/core/llm/test_llm_factory.py::test_llm_service_factory_create -v`
Expected: FAIL

- [ ] **Step 3: 实现工厂重构**

> **⚠️ 并发安全**: `create` 方法使用 `asyncio.Lock` 保护缓存读写，防止高并发下重复创建实例。
> **⚠️ 热更新优化**: 引入引用计数追踪活跃请求，替代固定 30 秒延迟清理，确保旧实例在所有引用释放后才销毁。
> **⚠️ 配置获取**: 通过 `config_manager.get_full_config()` 获取最新配置，避免 Python 模块缓存导致读取旧配置。
> **⚠️ 配置校验时机**: 配置变更事件触发时先校验新配置，校验通过后再清空缓存，避免无效配置导致实例创建失败。
> **⚠️ EventBus 异步回调修复**: `EventBus.publish()` 同步调用回调，需使用 `asyncio.get_running_loop().create_task()` 安全调度。
> **⚠️ ConfigChangedEvent 签名**: 使用 `event_bus.py` 实际签名 `(version_id, changed_keys)`，非 `(key, value)`。
> **⚠️ 双锁设计**: 使用 `_cache_lock` 保护缓存操作，`_config_lock` 保护配置变更处理，避免死锁。
> **⚠️ 优雅关闭**: 实现 `shutdown()` 方法，等待活跃请求完成后清理所有实例。
> **⚠️ 配置回滚**: 实例创建失败时恢复旧实例，避免服务中断。
> **⚠️ 锁超时**: 使用 `asyncio.wait_for()` 防止锁永久等待。
> **⚠️ 提供商参数过滤**: 不同提供商支持的参数不同（如 Ollama 不支持 `presence_penalty`），需按提供商白名单过滤，避免传参报错。

```python
import asyncio
from typing import Dict, Optional, Any, List
from injector import singleton

from src.config import ConfigManager
from src.core.event_bus import event_bus, ConfigChangedEvent
from src.core.llm.provider_registry import ProviderRegistry
from src.core.llm.config_validator import llm_config_validator
from src.utils.logger import logger

@singleton
class LLMServiceFactory:
    LOCK_TIMEOUT = 10.0  # 锁超时时间（秒）
    
    def __init__(self, config_manager: ConfigManager, provider_registry: ProviderRegistry):
        self.config_manager = config_manager
        self.provider_registry = provider_registry
        self._instances: Dict[str, Dict[str, Any]] = {}  # {scene: {framework: instance}}
        self._deprecated_instances: Dict[str, Dict[str, Any]] = {}  # {cache_key: {"instance": obj, "ref_count": int, "generation": int}}
        self._cache_lock = asyncio.Lock()  # 保护缓存操作
        self._config_lock = asyncio.Lock()  # 保护配置变更处理
        self._active_requests: Dict[str, int] = {}  # {cache_key: active_request_count}
        self._current_generation = 0  # 配置版本代际
        self._shutdown = False
        
        # 监听配置变更事件（EventBus原生支持异步回调调度）
        event_bus.subscribe(ConfigChangedEvent, self._on_config_changed)
    
    async def create(self, scene: str, framework: str = "langchain") -> Any:
        """创建指定场景的LLM服务实例（异步安全）"""
        if self._shutdown:
            raise RuntimeError("Factory is shutting down")
            
        cache_key = f"{scene}:{framework}"
        
        # 使用锁超时防止永久等待
        try:
            await asyncio.wait_for(self._cache_lock.acquire(), timeout=self.LOCK_TIMEOUT)
        except asyncio.TimeoutError:
            raise RuntimeError(f"Failed to acquire lock for {cache_key}")
        
        try:
            # 先检查缓存
            if scene in self._instances and framework in self._instances[scene]:
                self._active_requests[cache_key] = self._active_requests.get(cache_key, 0) + 1
                return self._instances[scene][framework]
            
            # 通过 config_manager 获取最新配置
            full_config = self.config_manager.get_full_config()
            scene_config_data = full_config.get(f"llm_{scene}", {})
            if not scene_config_data:
                raise ValueError(f"Unknown LLM scene: {scene}")
            
            # 使用 Pydantic 校验（复用 LLMSceneConfig 的约束）
            from src.config.modules.models.llm import LLMSceneConfig
            try:
                scene_config = LLMSceneConfig(**scene_config_data)
            except Exception as e:
                raise ValueError(f"Invalid LLM config for scene {scene}: {e}")
            
            # 获取提供商配置
            llm_providers = full_config.get("llm_llm_providers", {})
            provider_config = llm_providers.get(scene_config.provider)
            if not provider_config:
                raise ValueError(f"Unknown LLM provider: {scene_config.provider}")
            
            # 从注册表获取LLM类
            llm_cls = self.provider_registry.get(scene_config.provider, framework)
            if not llm_cls:
                raise ValueError(f"No adapter found for provider {scene_config.provider}, framework {framework}")
            
            # 按提供商白名单过滤参数（不同提供商支持的参数不同）
            PROVIDER_PARAM_WHITELIST = {
                "dashscope": {"model", "temperature", "max_tokens", "top_p", "presence_penalty", "frequency_penalty", "api_key", "base_url"},
                "openai": {"model", "temperature", "max_tokens", "top_p", "presence_penalty", "frequency_penalty", "api_key", "base_url"},
                "anthropic": {"model", "temperature", "max_tokens", "top_p", "presence_penalty", "frequency_penalty", "api_key", "base_url"},
                "deepseek": {"model", "temperature", "max_tokens", "top_p", "api_key", "base_url"},  # 不支持 penalty
                "ollama": {"model", "temperature", "max_tokens", "top_p", "base_url"},  # 不支持 penalty 和 api_key
            }
            allowed_params = PROVIDER_PARAM_WHITELIST.get(scene_config.provider, set())

            # 构造实例参数（仅保留提供商支持的参数）
            all_params = {
                "model": scene_config.model,
                "temperature": scene_config.temperature,
                "max_tokens": scene_config.max_tokens,
                "top_p": scene_config.top_p,
                "presence_penalty": scene_config.presence_penalty,
                "frequency_penalty": scene_config.frequency_penalty,
            }
            if provider_config.get("api_key"):
                all_params["api_key"] = provider_config["api_key"]
            if provider_config.get("base_url"):
                all_params["base_url"] = provider_config["base_url"]

            params = {k: v for k, v in all_params.items() if k in allowed_params}
            
            # 创建实例
            try:
                instance = llm_cls(**params)
            except Exception as e:
                # 实例创建失败，保留旧实例（若有）
                if scene in self._instances and framework in self._instances[scene]:
                    logger.error(f"Failed to create new LLM instance for {scene}: {e}, keeping old instance")
                    self._active_requests[cache_key] = self._active_requests.get(cache_key, 0) + 1
                    return self._instances[scene][framework]
                raise RuntimeError(f"Failed to create LLM instance for {scene}: {e}")
            
            # 缓存实例
            if scene not in self._instances:
                self._instances[scene] = {}
            self._instances[scene][framework] = instance
            self._active_requests[cache_key] = 1
            
            logger.info(f"Created LLM instance for scene {scene}, provider {scene_config.provider}, framework {framework}")
            return instance
        finally:
            self._cache_lock.release()
    
    async def release(self, scene: str, framework: str = "langchain"):
        """释放实例引用（调用方在使用完毕后调用）"""
        cache_key = f"{scene}:{framework}"
        try:
            await asyncio.wait_for(self._cache_lock.acquire(), timeout=self.LOCK_TIMEOUT)
        except asyncio.TimeoutError:
            logger.warning(f"Failed to acquire lock for release of {cache_key}")
            return
        
        try:
            count = self._active_requests.get(cache_key, 0)
            if count > 0:
                self._active_requests[cache_key] = count - 1
                # 引用计数归零时触发清理检查
                if self._active_requests[cache_key] == 0:
                    await self._try_cleanup_deprecated()
        finally:
            self._cache_lock.release()
    
    async def _on_config_changed(self, event: ConfigChangedEvent):
        """配置变更时重建实例（先校验新配置，再清空缓存）"""
        # 检查 changed_keys 是否包含 llm 相关配置
        changed_keys = getattr(event, 'changed_keys', [])
        if not any(key.startswith("llm") for key in changed_keys):
            return
        
        # 使用独立的配置锁，避免与缓存操作死锁
        try:
            await asyncio.wait_for(self._config_lock.acquire(), timeout=self.LOCK_TIMEOUT)
        except asyncio.TimeoutError:
            logger.warning("Failed to acquire config lock for hot reload")
            return
        
        try:
            # 先校验新配置
            try:
                full_config = self.config_manager.get_full_config()
                scene_names = ["report_generation", "assessment", "validation", "metadata_extraction", 
                               "query_rewrite", "query_routing", "content_generation", "vl_parsing", "ml_scoring"]
                
                from src.config.modules.models.llm import LLMSceneConfig
                for scene_name in scene_names:
                    scene_config_data = full_config.get(f"llm_{scene_name}", {})
                    if scene_config_data:
                        try:
                            LLMSceneConfig(**scene_config_data)
                        except Exception as e:
                            logger.error(f"Invalid config for scene {scene_name}: {e}")
                            return  # 拒绝无效配置，保留旧实例
            except Exception as e:
                logger.error(f"Failed to validate new config: {e}")
                return
            
            logger.info("LLM config changed and validated, starting instance rebuild...")
            
            # 增加代际计数
            self._current_generation += 1
            current_gen = self._current_generation
            
            # 标记旧实例为deprecated，使用代际计数追踪
            async with self._cache_lock:
                for scene, frameworks in self._instances.items():
                    for framework, instance in frameworks.items():
                        cache_key = f"{scene}:{framework}"
                        current_refs = self._active_requests.get(cache_key, 0)
                        self._deprecated_instances[cache_key] = {
                            "instance": instance,
                            "ref_count": current_refs,
                            "generation": current_gen - 1,  # 旧代际
                        }
                
                # 清空现有缓存
                self._instances.clear()
        finally:
            self._config_lock.release()
    
    async def _try_cleanup_deprecated(self):
        """尝试清理引用计数归零的废弃实例"""
        to_remove = []
        for cache_key, data in self._deprecated_instances.items():
            # 直接使用 cache_key 查找活跃请求计数
            current_ref = self._active_requests.get(cache_key, 0)
            if current_ref <= 0:
                instance = data["instance"]
                try:
                    # 显式释放资源（若支持）
                    if hasattr(instance, "dispose"):
                        if asyncio.iscoroutinefunction(instance.dispose):
                            await instance.dispose()
                        else:
                            instance.dispose()
                    logger.debug(f"Disposed deprecated LLM instance: {cache_key}")
                except Exception as e:
                    logger.warning(f"Failed to dispose instance {cache_key}: {e}")
                to_remove.append(cache_key)

        for cache_key in to_remove:
            del self._deprecated_instances[cache_key]

        if to_remove:
            logger.info(f"Cleaned up {len(to_remove)} deprecated LLM instances")
    
    async def shutdown(self):
        """优雅关闭：等待活跃请求完成后清理所有实例"""
        self._shutdown = True
        logger.info("LLMServiceFactory shutting down...")
        
        # 等待活跃请求完成（最多等待 30 秒）
        for _ in range(30):
            total_active = sum(self._active_requests.values())
            if total_active == 0:
                break
            await asyncio.sleep(1)
        
        # 强制清理所有实例
        async with self._cache_lock:
            for scene, frameworks in self._instances.items():
                for framework, instance in frameworks.items():
                    if hasattr(instance, "dispose"):
                        try:
                            if asyncio.iscoroutinefunction(instance.dispose):
                                await instance.dispose()
                            else:
                                instance.dispose()
                        except Exception as e:
                            logger.warning(f"Failed to dispose instance {scene}:{framework}: {e}")
            
            self._instances.clear()
            self._deprecated_instances.clear()
            self._active_requests.clear()
        
        logger.info("LLMServiceFactory shutdown complete")

# 通过 DI 容器获取实例
# llm_service_factory = injector.get(LLMServiceFactory)
```

**调用方使用示例**:
```python
# 获取实例（注意使用 await）
llm = await llm_service_factory.create("report_generation", framework="langchain")
try:
    response = await llm.chat(messages)
    # 处理响应...
finally:
    # 使用完毕后释放引用
    await llm_service_factory.release("report_generation", framework="langchain")
```

- [ ] **Step 4: 运行测试验证通过**
Run: `pytest tests/core/llm/test_llm_factory.py::test_llm_service_factory_create -v`
Expected: PASS



#### Task 1.2.3: 创建 EmbeddingFactory
**Files:**
- Create: `src/core/llm/embedding_factory.py`
- Test: `tests/core/llm/test_embedding_factory.py`

- [ ] **Step 1: 编写测试用例**

> **⚠️ 使用 pytest fixture**: 通过 `conftest.py` 注入工厂实例。

```python
import pytest

@pytest.mark.asyncio
async def test_embedding_factory_create(embedding_factory):
    # 测试创建LangChain Embedding实例
    embedding = await embedding_factory.create(framework="langchain")
    assert embedding is not None
    
    # 测试创建LlamaIndex Embedding实例
    embedding2 = await embedding_factory.create(framework="langchain")
    assert embedding is embedding2  # 缓存命中
    
    # 释放引用
    await embedding_factory.release(framework="langchain")
```

- [ ] **Step 2: 运行测试验证失败**
Run: `pytest tests/core/llm/test_embedding_factory.py::test_embedding_factory_create -v`
Expected: FAIL with "No module named 'src.core.llm.embedding_factory'"

- [ ] **Step 3: 实现EmbeddingFactory**

> **并发安全**: 使用 `asyncio.Lock` 保护实例创建，支持热更新。
> **引用计数**: 与 LLMServiceFactory 统一使用引用计数机制，确保热更新时不销毁正在使用的实例。
> **配置缓存**: 单次方法调用内缓存配置读取结果，避免重复调用 `config_manager`。
> **优雅关闭**: 实现 `shutdown()` 方法，清理所有实例。
> **EventBus 异步回调**: 使用同步包装器调度异步 handler。
> **dispose 支持**: 清理废弃实例时调用 `dispose()` 释放资源（如 GPU 内存）。

```python
import asyncio
from typing import Any, Optional, Dict
from injector import singleton

from src.config import ConfigManager
from src.core.event_bus import event_bus, ConfigChangedEvent
from src.utils.logger import logger

@singleton
class EmbeddingFactory:
    LOCK_TIMEOUT = 10.0
    
    def __init__(self, config_manager: ConfigManager):
        self.config_manager = config_manager
        self._langchain_instance: Optional[Any] = None
        self._llamaindex_instance: Optional[Any] = None
        self._cache_lock = asyncio.Lock()
        self._config_lock = asyncio.Lock()
        self._deprecated_instances: Dict[str, Any] = {}
        self._active_requests: Dict[str, int] = {}
        self._shutdown = False
        
        event_bus.subscribe(ConfigChangedEvent, self._on_config_changed_sync)
    
    async def create(self, framework: str = "langchain") -> Any:
        """创建Embedding实例（异步安全）"""
        if self._shutdown:
            raise RuntimeError("Factory is shutting down")
            
        cache_key = f"embedding:{framework}"
        
        try:
            await asyncio.wait_for(self._cache_lock.acquire(), timeout=self.LOCK_TIMEOUT)
        except asyncio.TimeoutError:
            raise RuntimeError(f"Failed to acquire lock for {cache_key}")
        
        try:
            # 检查缓存
            if framework == "langchain" and self._langchain_instance:
                self._active_requests[cache_key] = self._active_requests.get(cache_key, 0) + 1
                return self._langchain_instance
            elif framework == "llamaindex" and self._llamaindex_instance:
                self._active_requests[cache_key] = self._active_requests.get(cache_key, 0) + 1
                return self._llamaindex_instance
            
            # 获取最新配置（单次调用内缓存结果）
            full_config = self.config_manager.get_full_config()
            embedding_config = full_config.get("embedding", {})
            provider = embedding_config.get("provider", "dashscope")
            model = embedding_config.get("model", "text-embedding-v4")
            
            # 获取提供商凭证（缓存 llm_providers）
            llm_providers = full_config.get("llm_llm_providers", {})
            provider_creds = llm_providers.get(provider, {})
            
            if framework == "langchain":
                self._langchain_instance = await self._create_langchain_embedding(provider, model, provider_creds)
                self._active_requests[cache_key] = 1
                return self._langchain_instance
            
            elif framework == "llamaindex":
                self._llamaindex_instance = await self._create_llamaindex_embedding(provider, model, provider_creds)
                self._active_requests[cache_key] = 1
                return self._llamaindex_instance
            
            else:
                raise ValueError(f"Unsupported framework: {framework}")
        finally:
            self._cache_lock.release()
    
    async def release(self, framework: str = "langchain"):
        """释放实例引用"""
        cache_key = f"embedding:{framework}"
        try:
            await asyncio.wait_for(self._cache_lock.acquire(), timeout=self.LOCK_TIMEOUT)
        except asyncio.TimeoutError:
            logger.warning(f"Failed to acquire lock for release of {cache_key}")
            return
        
        try:
            count = self._active_requests.get(cache_key, 0)
            if count > 0:
                self._active_requests[cache_key] = count - 1
                if self._active_requests[cache_key] == 0:
                    await self._try_cleanup_deprecated()
        finally:
            self._cache_lock.release()
    
    async def _create_langchain_embedding(self, provider: str, model: str, provider_creds: dict) -> Any:
        if provider == "dashscope":
            from langchain_community.embeddings import DashScopeEmbeddings
            instance = DashScopeEmbeddings(
                model=model,
                dashscope_api_key=provider_creds.get("api_key", "")
            )
        elif provider == "openai":
            from langchain_openai import OpenAIEmbeddings
            instance = OpenAIEmbeddings(
                model=model,
                api_key=provider_creds.get("api_key", ""),
                base_url=provider_creds.get("base_url")
            )
        elif provider == "ollama":
            from langchain_ollama import OllamaEmbeddings
            instance = OllamaEmbeddings(
                model=model,
                base_url=provider_creds.get("base_url", "http://localhost:11434")
            )
        else:
            raise ValueError(f"Unsupported embedding provider: {provider}")
        
        logger.info(f"Created LangChain embedding instance, provider {provider}")
        return instance
    
    async def _create_llamaindex_embedding(self, provider: str, model: str, provider_creds: dict) -> Any:
        if provider == "dashscope":
            from llama_index.embeddings.dashscope import DashScopeEmbedding
            instance = DashScopeEmbedding(
                model_name=model,
                api_key=provider_creds.get("api_key", "")
            )
        elif provider == "openai":
            from llama_index.embeddings.openai import OpenAIEmbedding
            instance = OpenAIEmbedding(
                model=model,
                api_key=provider_creds.get("api_key", ""),
                base_url=provider_creds.get("base_url")
            )
        elif provider == "ollama":
            from llama_index.embeddings.ollama import OllamaEmbedding
            instance = OllamaEmbedding(
                model_name=model,
                base_url=provider_creds.get("base_url", "http://localhost:11434")
            )
        else:
            raise ValueError(f"Unsupported embedding provider: {provider}")
        
        logger.info(f"Created LlamaIndex embedding instance, provider {provider}")
        return instance
    
    def _on_config_changed_sync(self, event: ConfigChangedEvent):
        """配置变更事件同步入口（安全调度异步 handler）"""
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self._on_config_changed(event))
        except RuntimeError:
            logger.warning("EmbeddingFactory config change skipped: no running event loop")
    
    async def _on_config_changed(self, event: ConfigChangedEvent):
        """配置变更时先校验新配置，再标记旧实例为废弃"""
        changed_keys = getattr(event, 'changed_keys', [])
        if not any(key.startswith("embedding") or key.startswith("llm_llm_providers") for key in changed_keys):
            return

        # 先校验新配置，校验通过后再清空缓存
        try:
            full_config = self.config_manager.get_full_config()
            embedding_config = full_config.get("embedding", {})
            provider = embedding_config.get("provider", "dashscope")
            model = embedding_config.get("model", "text-embedding-v4")
            if provider not in ("dashscope", "openai", "ollama"):
                logger.error(f"Invalid embedding provider: {provider}, rejecting config change")
                return
            if not model or not isinstance(model, str):
                logger.error(f"Invalid embedding model: {model}, rejecting config change")
                return
        except Exception as e:
            logger.error(f"Failed to validate new embedding config: {e}")
            return  # 拒绝无效配置，保留旧实例

        try:
            await asyncio.wait_for(self._config_lock.acquire(), timeout=self.LOCK_TIMEOUT)
        except asyncio.TimeoutError:
            logger.warning("Failed to acquire config lock for embedding hot reload")
            return

        try:
            async with self._cache_lock:
                if self._langchain_instance:
                    instance_id = f"langchain_{id(self._langchain_instance)}"
                    self._deprecated_instances[instance_id] = {
                        "instance": self._langchain_instance,
                        "ref_count": self._active_requests.get("embedding:langchain", 0)
                    }
                    self._langchain_instance = None
                if self._llamaindex_instance:
                    instance_id = f"llamaindex_{id(self._llamaindex_instance)}"
                    self._deprecated_instances[instance_id] = {
                        "instance": self._llamaindex_instance,
                        "ref_count": self._active_requests.get("embedding:llamaindex", 0)
                    }
                    self._llamaindex_instance = None
                logger.info("Embedding config changed and validated, instances marked deprecated")
        finally:
            self._config_lock.release()
    
    async def _try_cleanup_deprecated(self):
        """清理引用计数归零的废弃实例（含 dispose 调用）"""
        to_remove = []
        for instance_id, data in self._deprecated_instances.items():
            if data["ref_count"] <= 0:
                instance = data["instance"]
                try:
                    if hasattr(instance, "dispose"):
                        if asyncio.iscoroutinefunction(instance.dispose):
                            await instance.dispose()
                        else:
                            instance.dispose()
                    logger.debug(f"Disposed deprecated embedding instance: {instance_id}")
                except Exception as e:
                    logger.warning(f"Failed to dispose embedding instance {instance_id}: {e}")
                to_remove.append(instance_id)
        
        for instance_id in to_remove:
            del self._deprecated_instances[instance_id]
        
        if to_remove:
            logger.info(f"Cleaned up {len(to_remove)} deprecated embedding instances")
    
    async def shutdown(self):
        """优雅关闭"""
        self._shutdown = True
        async with self._cache_lock:
            for instance in [self._langchain_instance, self._llamaindex_instance]:
                if instance and hasattr(instance, "dispose"):
                    try:
                        if asyncio.iscoroutinefunction(instance.dispose):
                            await instance.dispose()
                        else:
                            instance.dispose()
                    except Exception as e:
                        logger.warning(f"Failed to dispose embedding instance: {e}")
            self._langchain_instance = None
            self._llamaindex_instance = None
            self._deprecated_instances.clear()
            self._active_requests.clear()

# 通过 DI 容器获取实例
# embedding_factory = injector.get(EmbeddingFactory)
```

- [ ] **Step 4: 运行测试验证通过**
Run: `pytest tests/core/llm/test_embedding_factory.py::test_embedding_factory_create -v`
Expected: PASS



#### Task 1.2.4: 创建 RerankerFactory 接口
**Files:**
- Create: `src/core/llm/reranker_factory.py`
- Test: `tests/core/llm/test_reranker_factory.py`

- [ ] **Step 1: 编写测试用例**

> **⚠️ 使用 pytest fixture**: 通过 `conftest.py` 注入工厂实例。

```python
import pytest

@pytest.mark.asyncio
async def test_reranker_factory_create(reranker_factory):
    # 测试创建本地Reranker实例
    reranker = await reranker_factory.create()
    assert reranker is not None
    
    # 验证缓存命中
    reranker2 = await reranker_factory.create()
    assert reranker is reranker2
    
    # 释放引用
    await reranker_factory.release()
```

- [ ] **Step 2: 运行测试验证失败**
Run: `pytest tests/core/llm/test_reranker_factory.py::test_reranker_factory_create -v`
Expected: FAIL with "No module named 'src.core.llm.reranker_factory'"

- [ ] **Step 3: 实现RerankerFactory**

> **并发安全**: 使用 `asyncio.Lock` 保护实例创建，支持热更新。
> **引用计数**: 与 LLMServiceFactory 统一使用引用计数机制。
> **非阻塞模型加载**: CrossEncoder 模型加载使用 `asyncio.to_thread()` 避免阻塞事件循环。
> **EventBus 异步回调**: 使用同步包装器调度异步 handler。
> **优雅关闭**: 实现 `shutdown()` 方法。

```python
import asyncio
from typing import Any, Optional, Dict
from injector import singleton

from src.config import ConfigManager
from src.core.event_bus import event_bus, ConfigChangedEvent
from src.utils.logger import logger

@singleton
class RerankerFactory:
    LOCK_TIMEOUT = 10.0
    
    def __init__(self, config_manager: ConfigManager):
        self.config_manager = config_manager
        self._instance: Optional[Any] = None
        self._cache_lock = asyncio.Lock()
        self._config_lock = asyncio.Lock()
        self._deprecated_instances: Dict[str, Any] = {}
        self._active_requests: Dict[str, int] = {}
        self._shutdown = False
        
        event_bus.subscribe(ConfigChangedEvent, self._on_config_changed_sync)
    
    async def create(self) -> Any:
        """创建Reranker实例（异步安全）"""
        if self._shutdown:
            raise RuntimeError("Factory is shutting down")
            
        cache_key = "reranker:default"
        
        try:
            await asyncio.wait_for(self._cache_lock.acquire(), timeout=self.LOCK_TIMEOUT)
        except asyncio.TimeoutError:
            raise RuntimeError("Failed to acquire lock for reranker")
        
        try:
            if self._instance:
                self._active_requests[cache_key] = self._active_requests.get(cache_key, 0) + 1
                return self._instance
            
            full_config = self.config_manager.get_full_config()
            retrieval_config = full_config.get("rag_retrieval", {})
            provider = retrieval_config.get("reranker_provider", "local")
            model = retrieval_config.get("reranker_model", "BAAI/bge-reranker-v2-m3")
            
            if provider == "local":
                # 使用 asyncio.to_thread 避免阻塞事件循环
                self._instance = await asyncio.to_thread(self._load_cross_encoder, model)
            else:
                raise ValueError(f"Unsupported reranker provider: {provider}")
            
            self._active_requests[cache_key] = 1
            logger.info(f"Created reranker instance, provider {provider}")
            return self._instance
        finally:
            self._cache_lock.release()
    
    def _load_cross_encoder(self, model_name: str) -> Any:
        """在独立线程中加载 CrossEncoder 模型"""
        from sentence_transformers import CrossEncoder
        return CrossEncoder(model_name, max_length=512)
    
    async def release(self):
        """释放实例引用"""
        cache_key = "reranker:default"
        try:
            await asyncio.wait_for(self._cache_lock.acquire(), timeout=self.LOCK_TIMEOUT)
        except asyncio.TimeoutError:
            logger.warning("Failed to acquire lock for reranker release")
            return
        
        try:
            count = self._active_requests.get(cache_key, 0)
            if count > 0:
                self._active_requests[cache_key] = count - 1
                if self._active_requests[cache_key] == 0:
                    await self._try_cleanup_deprecated()
        finally:
            self._cache_lock.release()
    
    def _on_config_changed_sync(self, event: ConfigChangedEvent):
        """配置变更事件同步入口（安全调度异步 handler）"""
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self._on_config_changed(event))
        except RuntimeError:
            logger.warning("RerankerFactory config change skipped: no running event loop")
    
    async def _on_config_changed(self, event: ConfigChangedEvent):
        """配置变更时标记旧实例为废弃"""
        changed_keys = getattr(event, 'changed_keys', [])
        if not any("reranker" in key for key in changed_keys):
            return
            
        try:
            await asyncio.wait_for(self._config_lock.acquire(), timeout=self.LOCK_TIMEOUT)
        except asyncio.TimeoutError:
            logger.warning("Failed to acquire config lock for reranker hot reload")
            return
        
        try:
            async with self._cache_lock:
                if self._instance:
                    instance_id = f"reranker_{id(self._instance)}"
                    self._deprecated_instances[instance_id] = {
                        "instance": self._instance,
                        "ref_count": self._active_requests.get("reranker:default", 0)
                    }
                    self._instance = None
                    logger.info("Reranker config changed, instance marked deprecated")
        finally:
            self._config_lock.release()
    
    async def _try_cleanup_deprecated(self):
        """清理引用计数归零的废弃实例"""
        to_remove = []
        for instance_id, data in self._deprecated_instances.items():
            if data["ref_count"] <= 0:
                instance = data["instance"]
                try:
                    if hasattr(instance, "dispose"):
                        if asyncio.iscoroutinefunction(instance.dispose):
                            await instance.dispose()
                        else:
                            instance.dispose()
                    logger.debug(f"Disposed deprecated reranker instance: {instance_id}")
                except Exception as e:
                    logger.warning(f"Failed to dispose reranker instance {instance_id}: {e}")
                to_remove.append(instance_id)
        
        for instance_id in to_remove:
            del self._deprecated_instances[instance_id]
        
        if to_remove:
            logger.info(f"Cleaned up {len(to_remove)} deprecated reranker instances")
    
    async def shutdown(self):
        """优雅关闭"""
        self._shutdown = True
        async with self._cache_lock:
            if self._instance and hasattr(self._instance, "dispose"):
                try:
                    if asyncio.iscoroutinefunction(self._instance.dispose):
                        await self._instance.dispose()
                    else:
                        self._instance.dispose()
                except Exception as e:
                    logger.warning(f"Failed to dispose reranker instance: {e}")
            self._instance = None
            self._deprecated_instances.clear()
            self._active_requests.clear()

# 通过 DI 容器获取实例
# reranker_factory = injector.get(RerankerFactory)
```

- [ ] **Step 4: 运行测试验证通过**
Run: `pytest tests/core/llm/test_reranker_factory.py::test_reranker_factory_create -v`
Expected: PASS

#### Task 1.2.5: 更新 `__init__.py` 导出 + EventBus 异步支持
**Files:**
- Create: `src/core/llm/__init__.py` (update)
- Modify: `src/core/event_bus.py`

- [ ] **Step 1: 更新 `__init__.py` 导出**

> **⚠️ 模块导出**: 确保新创建的类可通过 `src.core.llm` 导入。

```python
# src/core/llm/__init__.py
from src.core.llm.provider_registry import ProviderRegistry
from src.core.llm.factory import LLMServiceFactory
from src.core.llm.embedding_factory import EmbeddingFactory
from src.core.llm.reranker_factory import RerankerFactory
from src.core.llm.config_validator import LLMConfigValidator, llm_config_validator

__all__ = [
    "ProviderRegistry",
    "LLMServiceFactory",
    "EmbeddingFactory",
    "RerankerFactory",
    "LLMConfigValidator",
    "llm_config_validator",
]
```

- [ ] **Step 2: 修复 EventBus 异步回调支持**

> **⚠️ EventBus 异步回调修复**: `EventBus.publish()` 同步调用回调，异步 handler 需使用 `asyncio.create_task()` 调度。
> 工厂类已通过 `_on_config_changed_sync()` 包装器处理，此处为 EventBus 本身增加 async 感知能力。

```python
# src/core/event_bus.py - 修改 publish 方法
import asyncio
import inspect

@classmethod
def publish(cls, event: BaseEvent) -> None:
    """发布事件（内存 + Redis Pub/Sub）"""
    event_type = type(event)
    for callback in cls._subscribers.get(event_type, []):
        try:
            # 异步回调：检查 event loop 是否存在，安全调度
            if asyncio.iscoroutinefunction(callback):
                try:
                    loop = asyncio.get_running_loop()
                    loop.create_task(callback(event))
                except RuntimeError:
                    # 无运行中的 event loop，记录警告并跳过
                    logger.warning(f"Async event callback for {event_type.__name__} skipped: no running event loop")
            else:
                callback(event)
        except Exception as e:
            logger.error(f"Event callback failed for {event_type.__name__}: {e}")
    # ... Redis Pub/Sub 部分保持不变
```

> **注意**: 工厂类不再需要 `_on_config_changed_sync` 包装器，直接使用EventBus原生异步回调支持即可。
