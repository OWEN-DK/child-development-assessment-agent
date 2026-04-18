"""Embedding 工厂 - 支持多提供商和热更新"""

import asyncio
from typing import Any, Optional, Dict
from injector import singleton

from src.config.core.manager import ConfigManager
from src.core.event_bus import event_bus, ConfigChangedEvent
from src.utils.logger import logger


@singleton
class EmbeddingFactory:
    """Embedding 工厂（支持多提供商和热更新）"""

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

        # 监听配置变更事件
        event_bus.subscribe(ConfigChangedEvent, self._on_config_changed_sync)

    async def create(self, framework: str = "langchain") -> Any:
        """创建 Embedding 实例（异步安全）

        Args:
            framework: 框架名称（langchain 或 llamaindex）

        Returns:
            Embedding 实例

        Raises:
            RuntimeError: 工厂正在关闭
            ValueError: 不支持的框架或提供商
        """
        if self._shutdown:
            raise RuntimeError("Factory is shutting down")

        cache_key = f"embedding:{framework}"

        try:
            await asyncio.wait_for(
                self._cache_lock.acquire(), timeout=self.LOCK_TIMEOUT
            )
        except asyncio.TimeoutError:
            raise RuntimeError(f"Failed to acquire lock for {cache_key}")

        try:
            # 检查缓存
            if framework == "langchain" and self._langchain_instance:
                self._active_requests[cache_key] = (
                    self._active_requests.get(cache_key, 0) + 1
                )
                return self._langchain_instance
            elif framework == "llamaindex" and self._llamaindex_instance:
                self._active_requests[cache_key] = (
                    self._active_requests.get(cache_key, 0) + 1
                )
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
                self._langchain_instance = await self._create_langchain_embedding(
                    provider, model, provider_creds
                )
                self._active_requests[cache_key] = 1
                return self._langchain_instance

            elif framework == "llamaindex":
                self._llamaindex_instance = await self._create_llamaindex_embedding(
                    provider, model, provider_creds
                )
                self._active_requests[cache_key] = 1
                return self._llamaindex_instance

            else:
                raise ValueError(f"Unsupported framework: {framework}")
        finally:
            self._cache_lock.release()

    async def release(self, framework: str = "langchain"):
        """释放实例引用

        Args:
            framework: 框架名称
        """
        cache_key = f"embedding:{framework}"
        try:
            await asyncio.wait_for(
                self._cache_lock.acquire(), timeout=self.LOCK_TIMEOUT
            )
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

    async def _create_langchain_embedding(
        self, provider: str, model: str, provider_creds: dict
    ) -> Any:
        """创建 LangChain Embedding 实例"""
        if provider == "dashscope":
            from langchain_community.embeddings import DashScopeEmbeddings

            instance = DashScopeEmbeddings(
                model=model, dashscope_api_key=provider_creds.get("api_key", "")
            )
        elif provider == "openai":
            from langchain_openai import OpenAIEmbeddings

            instance = OpenAIEmbeddings(
                model=model,
                api_key=provider_creds.get("api_key", ""),
                base_url=provider_creds.get("base_url"),
            )
        elif provider == "ollama":
            from langchain_ollama import OllamaEmbeddings

            instance = OllamaEmbeddings(
                model=model,
                base_url=provider_creds.get("base_url", "http://localhost:11434"),
            )
        else:
            raise ValueError(f"Unsupported embedding provider: {provider}")

        logger.info(f"Created LangChain embedding instance, provider {provider}")
        return instance

    async def _create_llamaindex_embedding(
        self, provider: str, model: str, provider_creds: dict
    ) -> Any:
        """创建 LlamaIndex Embedding 实例"""
        if provider == "dashscope":
            from llama_index.embeddings.dashscope import DashScopeEmbedding

            instance = DashScopeEmbedding(
                model_name=model, api_key=provider_creds.get("api_key", "")
            )
        elif provider == "openai":
            from llama_index.embeddings.openai import OpenAIEmbedding

            instance = OpenAIEmbedding(
                model=model,
                api_key=provider_creds.get("api_key", ""),
                base_url=provider_creds.get("base_url"),
            )
        elif provider == "ollama":
            from llama_index.embeddings.ollama import OllamaEmbedding

            instance = OllamaEmbedding(
                model_name=model,
                base_url=provider_creds.get("base_url", "http://localhost:11434"),
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
            logger.warning(
                "EmbeddingFactory config change skipped: no running event loop"
            )

    async def _on_config_changed(self, event: ConfigChangedEvent):
        """配置变更时先校验新配置，再标记旧实例为废弃"""
        changed_keys = getattr(event, "changed_keys", [])
        if not any(
            key.startswith("embedding") or key.startswith("llm_llm_providers")
            for key in changed_keys
        ):
            return

        # 先校验新配置，校验通过后再清空缓存
        try:
            full_config = self.config_manager.get_full_config()
            embedding_config = full_config.get("embedding", {})
            provider = embedding_config.get("provider", "dashscope")
            model = embedding_config.get("model", "text-embedding-v4")
            if provider not in ("dashscope", "openai", "ollama"):
                logger.error(
                    f"Invalid embedding provider: {provider}, rejecting config change"
                )
                return
            if not model or not isinstance(model, str):
                logger.error(
                    f"Invalid embedding model: {model}, rejecting config change"
                )
                return
        except Exception as e:
            logger.error(f"Failed to validate new embedding config: {e}")
            return  # 拒绝无效配置，保留旧实例

        try:
            await asyncio.wait_for(
                self._config_lock.acquire(), timeout=self.LOCK_TIMEOUT
            )
        except asyncio.TimeoutError:
            logger.warning("Failed to acquire config lock for embedding hot reload")
            return

        try:
            async with self._cache_lock:
                if self._langchain_instance:
                    instance_id = f"langchain_{id(self._langchain_instance)}"
                    self._deprecated_instances[instance_id] = {
                        "instance": self._langchain_instance,
                        "ref_count": self._active_requests.get(
                            "embedding:langchain", 0
                        ),
                    }
                    self._langchain_instance = None
                if self._llamaindex_instance:
                    instance_id = f"llamaindex_{id(self._llamaindex_instance)}"
                    self._deprecated_instances[instance_id] = {
                        "instance": self._llamaindex_instance,
                        "ref_count": self._active_requests.get(
                            "embedding:llamaindex", 0
                        ),
                    }
                    self._llamaindex_instance = None
                logger.info(
                    "Embedding config changed and validated, instances marked deprecated"
                )
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
                    logger.debug(
                        f"Disposed deprecated embedding instance: {instance_id}"
                    )
                except Exception as e:
                    logger.warning(
                        f"Failed to dispose embedding instance {instance_id}: {e}"
                    )
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
