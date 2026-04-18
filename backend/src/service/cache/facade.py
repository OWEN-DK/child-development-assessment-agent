import asyncio
import time
from collections import defaultdict
from typing import Any, List, Optional

from cachetools import LRUCache

from src.config import settings
from src.core.circuit_breaker import mysql_circuit_breaker
from src.core.interfaces import ICacheService
from src.service.cache.disk_cache import DiskCache
from src.service.cache.redis_cache import RedisCache
from src.utils.logger import logger


class CacheCore:
    def __init__(self):
        self.enabled = settings.rag_config["cache"]["enabled"]
        self.memory_cache = LRUCache(maxsize=settings.rag_config["cache"]["max_size"] or 10000)
        self.redis_cache = RedisCache()
        self.disk_cache = DiskCache()
        self.bloom_filter = None
        self.locks = {}
        self.doc_hash_map = defaultdict(set)
        self.tag_map = defaultdict(set)
        self.default_ttl = settings.rag_config["cache"]["ttl_seconds"]

    def _get_cache_key(self, key_prefix: str, args: tuple, kwargs: dict) -> str:
        import hashlib
        import json
        key_parts = args + tuple(sorted(kwargs.items()))
        key_hash = hashlib.md5(json.dumps(key_parts, sort_keys=True, ensure_ascii=False, default=lambda obj: obj.isoformat() if hasattr(obj, "isoformat") else str(obj)).encode()).hexdigest()
        return f"rag:cache:{key_prefix}:{key_hash}"

    async def get(self, key: str, default: Any = None) -> Any:
        if not self.enabled:
            return default
        if key in self.memory_cache:
            logger.debug(f"内存缓存命中: {key}")
            return self.memory_cache[key]
        disk_value = self.disk_cache.get(key)
        if disk_value is not None:
            self.memory_cache[key] = disk_value
            logger.debug(f"磁盘缓存命中: {key}")
            return disk_value
        redis_value = await self.redis_cache.get(key)
        if redis_value:
            import json
            value = json.loads(redis_value)
            self.memory_cache[key] = value
            logger.debug(f"Redis缓存命中: {key}")
            return value
        return default

    async def set(self, key: str, value: Any, expire: int = None, doc_hashes: Optional[List[str]] = None, tags: Optional[List[str]] = None, is_hot: bool = False):
        if not self.enabled:
            return
        expire = expire or self.default_ttl
        expire += int(time.time()) % 60
        self.memory_cache[key] = value
        self.disk_cache.set(key, value)
        import json
        serialized = json.dumps(value, ensure_ascii=False, default=lambda obj: obj.isoformat() if hasattr(obj, "isoformat") else str(obj))
        await self.redis_cache.set(key, serialized, expire)
        if doc_hashes:
            for doc_hash in doc_hashes:
                self.doc_hash_map[doc_hash].add(key)
                await self.redis_cache.sadd(f"rag:doc_map:{doc_hash}", key)
        if tags:
            for tag in tags:
                self.tag_map[tag].add(key)
                await self.redis_cache.sadd(f"rag:tag_map:{tag}", key)

    async def set_with_jitter(self, key: str, value: Any, base_ttl: int = None, tags: list[str] = None) -> None:
        import random
        base_ttl = base_ttl or self.default_ttl
        jitter = int(base_ttl * 0.2)
        actual_ttl = base_ttl + random.randint(-jitter, jitter)
        actual_ttl = max(60, actual_ttl)
        await self.set(key, value, expire=actual_ttl, tags=tags)

    async def delete(self, key: str) -> None:
        if key in self.memory_cache:
            del self.memory_cache[key]
        self.disk_cache.delete(key)
        await self.redis_cache.delete(key)

    async def invalidate_tag(self, tag: str) -> None:
        if tag not in self.tag_map:
            return
        keys = self.tag_map[tag]
        if not keys:
            return
        for key in keys:
            if key in self.memory_cache:
                del self.memory_cache[key]
        await self.redis_cache.delete_many(*keys)
        del self.tag_map[tag]

    async def clear_all(self) -> None:
        self.memory_cache.clear()
        self.disk_cache.clear()
        await self.redis_cache.flushdb()
        logger.info("所有缓存已清空")

    def clear(self):
        self.memory_cache.clear()
        self.doc_hash_map.clear()
        self.tag_map.clear()
        self.locks.clear()
        self.disk_cache.clear()
        logger.info("All cache cleared")

    def get_cache_stats(self) -> dict:
        return {
            "enabled": self.enabled,
            "memory_cache_size": len(getattr(self.memory_cache, "cache", self.memory_cache)),
            "disk_cache_size": len(self.disk_cache.disk_cache) if self.disk_cache.is_enabled() else 0,
            "disk_cache_enabled": self.disk_cache.is_enabled(),
            "disk_cache_dir": self.disk_cache.disk_cache_dir,
            "max_size": settings.rag_config["cache"]["max_size"],
            "default_ttl": self.default_ttl,
            "redis_enabled": self.redis_cache.redis_client is not None,
            "bloom_filter_enabled": self.bloom_filter is not None,
            "doc_hash_count": len(self.doc_hash_map),
            "tag_count": len(self.tag_map),
        }


class CacheProtection(CacheCore):
    async def get_with_protection(self, key: str, query_func, ttl: int = None) -> Any:
        value = await self.get(key)
        if value is not None:
            return value if value != "__NULL__" else None
        result = await mysql_circuit_breaker.execute(query_func)
        if result is None:
            await self.set(key, "__NULL__", expire=300)
        else:
            await self.set_with_jitter(key, result, base_ttl=ttl or self.default_ttl)
        return result

    async def get_with_lock(self, key: str, query_func, ttl: int = None) -> Any:
        value = await self.get(key)
        if value is not None:
            return value if value != "__NULL__" else None
        lock_key = f"lock:cache:{key}"
        acquired = await self.redis_cache.set_lock(lock_key, "1", ex=10)
        if acquired:
            try:
                result = await mysql_circuit_breaker.execute(query_func)
                if result is None:
                    await self.set(key, "__NULL__", expire=300)
                else:
                    await self.set_with_jitter(key, result, base_ttl=ttl or self.default_ttl)
                return result
            finally:
                await self.redis_cache.delete_lock(lock_key)
        else:
            await asyncio.sleep(0.1)
            return await self.get_with_lock(key, query_func, ttl)

    async def get_with_logical_expiry(self, key: str, query_func, physical_ttl: int = 86400) -> Any:
        cached = await self.get(key)
        if cached:
            if isinstance(cached, dict) and "logical_expire" in cached:
                if time.time() < cached.get("logical_expire", 0):
                    return cached["value"]
                else:
                    asyncio.create_task(self._refresh_cache(key, query_func, physical_ttl))
                    return cached["value"]
        return await self._refresh_cache(key, query_func, physical_ttl)

    async def _refresh_cache(self, key: str, query_func, physical_ttl: int) -> Any:
        result = await mysql_circuit_breaker.execute(query_func)
        data = {"value": result, "logical_expire": time.time() + self.default_ttl}
        await self.set(key, data, expire=physical_ttl)
        return result

    async def invalidate_by_doc_hash(self, doc_hash: str):
        if not self.enabled:
            return
        keys_to_remove = self.doc_hash_map.pop(doc_hash, set())
        redis_keys = await self.redis_cache.smembers(f"rag:doc_map:{doc_hash}")
        keys_to_remove.update(redis_keys)
        await self.redis_cache.delete(f"rag:doc_map:{doc_hash}")
        for key in keys_to_remove:
            if key in self.memory_cache:
                del self.memory_cache[key]
            await self.redis_cache.delete(key)
        logger.info(f"Invalidated {len(keys_to_remove)} cache entries for doc hash {doc_hash}")

    async def invalidate_by_tag(self, tag: str):
        if not self.enabled:
            return
        keys_to_remove = self.tag_map.pop(tag, set())
        redis_keys = await self.redis_cache.smembers(f"rag:tag_map:{tag}")
        keys_to_remove.update(redis_keys)
        await self.redis_cache.delete(f"rag:tag_map:{tag}")
        for key in keys_to_remove:
            if key in self.memory_cache:
                del self.memory_cache[key]
            await self.redis_cache.delete(key)


class CacheFacade(CacheProtection, ICacheService):
    pass


def cached(expire: int = None, key_prefix: str = "", doc_hash_param: Optional[str] = None, tags: Optional[List[str]] = None, is_hot: bool = False):
    from functools import wraps
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            from src.service.cache_service import cache_service
            cache_key = cache_service._get_cache_key(key_prefix, args, kwargs)
            doc_hashes = [kwargs[doc_hash_param]] if doc_hash_param and doc_hash_param in kwargs else None
            async def load_func():
                return await func(*args, **kwargs)
            return await cache_service.get_with_protection(cache_key, load_func, expire=expire, doc_hashes=doc_hashes, tags=tags, is_hot=is_hot)
        return wrapper
    return decorator


cache_service = CacheFacade()
