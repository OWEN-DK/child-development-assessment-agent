"""Reranker 工厂 - 支持热更新"""

import asyncio
from typing import Any, Optional, Dict
from injector import singleton

from src.config.core.manager import ConfigManager
from src.core.event_bus import event_bus, ConfigChangedEvent
from src.utils.logger import logger


@singleton
class RerankerFactory:
    """Reranker 工厂（支持热更新）"""

    LOCK_TIMEOUT = 10.0

    def __init__(self, config_manager: ConfigManager):
        self.config_manager = config_manager
        self._instance: Optional[Any] = None
        self._cache_lock = asyncio.Lock()
        self._config_lock = asyncio.Lock()
        self._deprecated_instances: Dict[str, Any] = {}
        self._active_requests: Dict[str, int] = {}
        self._shutdown = False

        # 监听配置变更事件
        event_bus.subscribe(ConfigChangedEvent, self._on_config_changed_sync)

    async def create(self) -> Any:
        """创建 Reranker 实例（异步安全）

        Returns:
            Reranker 实例（CrossEncoder）

        Raises:
            RuntimeError: 工厂正在关闭
            ValueError: 不支持的提供商
        """
        if self._shutdown:
            raise RuntimeError("Factory is shutting down")

        cache_key = "reranker:default"

        try:
            await asyncio.wait_for(
                self._cache_lock.acquire(), timeout=self.LOCK_TIMEOUT
            )
        except asyncio.TimeoutError:
            raise RuntimeError("Failed to acquire lock for reranker")

        try:
            if self._instance:
                self._active_requests[cache_key] = (
                    self._active_requests.get(cache_key, 0) + 1
                )
                return self._instance

            full_config = self.config_manager.get_full_config()
            retrieval_config = full_config.get("rag_retrieval", {})
            provider = retrieval_config.get("reranker_provider", "local")
            model = retrieval_config.get("reranker_model", "BAAI/bge-reranker-v2-m3")

            if provider == "local":
                # 使用 asyncio.to_thread 避免阻塞事件循环
                self._instance = await asyncio.to_thread(
                    self._load_cross_encoder, model
                )
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
            await asyncio.wait_for(
                self._cache_lock.acquire(), timeout=self.LOCK_TIMEOUT
            )
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
            logger.warning(
                "RerankerFactory config change skipped: no running event loop"
            )

    async def _on_config_changed(self, event: ConfigChangedEvent):
        """配置变更时标记旧实例为废弃"""
        changed_keys = getattr(event, "changed_keys", [])
        if not any("reranker" in key for key in changed_keys):
            return

        try:
            await asyncio.wait_for(
                self._config_lock.acquire(), timeout=self.LOCK_TIMEOUT
            )
        except asyncio.TimeoutError:
            logger.warning("Failed to acquire config lock for reranker hot reload")
            return

        try:
            async with self._cache_lock:
                if self._instance:
                    instance_id = f"reranker_{id(self._instance)}"
                    self._deprecated_instances[instance_id] = {
                        "instance": self._instance,
                        "ref_count": self._active_requests.get("reranker:default", 0),
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
                    logger.debug(
                        f"Disposed deprecated reranker instance: {instance_id}"
                    )
                except Exception as e:
                    logger.warning(
                        f"Failed to dispose reranker instance {instance_id}: {e}"
                    )
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
