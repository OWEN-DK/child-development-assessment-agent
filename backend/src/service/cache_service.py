import time
from typing import Any, Tuple, Optional
from src.config.settings import settings
from src.utils.logger import logger


class CacheService:
    """缓存服务，管理检索结果的缓存"""

    def __init__(self):
        self.cache = {}
        self.cache_timestamps = {}
        self.enabled = settings.rag_config["cache"]["enabled"]
        self.max_size = settings.rag_config["cache"]["max_size"]
        self.ttl_seconds = settings.rag_config["cache"]["ttl_seconds"]

    def get(self, key: Tuple[str, int, int]) -> Optional[Any]:
        """从缓存获取结果"""
        if not self.enabled:
            return None

        if key in self.cache and key in self.cache_timestamps:
            timestamp = self.cache_timestamps[key]
            if time.time() - timestamp < self.ttl_seconds:
                logger.debug(f"Cache hit for key: {key}")
                return self.cache[key]
            else:
                # 移除过期条目
                del self.cache[key]
                del self.cache_timestamps[key]

        return None

    def set(self, key: Tuple[str, int, int], value: Any):
        """保存结果到缓存"""
        if not self.enabled:
            return

        # LRU淘汰：如果缓存已满，删除最旧的条目
        if len(self.cache) >= self.max_size:
            oldest_key = min(
                self.cache_timestamps.keys(), key=lambda k: self.cache_timestamps[k]
            )
            del self.cache[oldest_key]
            del self.cache_timestamps[oldest_key]
            logger.debug(f"Evicted oldest cache entry: {oldest_key}")

        self.cache[key] = value
        self.cache_timestamps[key] = time.time()
        logger.debug(f"Cached result for key: {key}")

    def clear(self):
        """清空所有缓存"""
        self.cache.clear()
        self.cache_timestamps.clear()
        logger.info("Cache cleared")

    def get_cache_stats(self) -> dict:
        """获取缓存统计信息"""
        return {
            "enabled": self.enabled,
            "size": len(self.cache),
            "max_size": self.max_size,
            "ttl_seconds": self.ttl_seconds,
        }
