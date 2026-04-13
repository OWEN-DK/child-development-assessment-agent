import hashlib
import json
import time
import asyncio
import random
import os
from pathlib import Path
from typing import Any, Optional, List, Set
from collections import defaultdict
from functools import wraps
from cachetools import LRUCache
from src.config import settings, redis_settings
from src.core.redis_client import RedisClient
from src.core.circuit_breaker import redis_circuit_breaker, mysql_circuit_breaker
from src.core.interfaces import ICacheService
from src.utils.logger import logger

try:
    from lru import LRU
except ImportError:

    class LRU:
        def __init__(self, maxsize):
            self.maxsize = maxsize
            self.cache = {}
            self.timestamps = {}

        def __contains__(self, key):
            return key in self.cache

        def __getitem__(self, key):
            if key in self.cache:
                self.timestamps[key] = time.time()
                return self.cache[key]
            raise KeyError(key)

        def __setitem__(self, key, value):
            if len(self.cache) >= self.maxsize:
                oldest_key = min(
                    self.timestamps.keys(), key=lambda k: self.timestamps[k]
                )
                del self.cache[oldest_key]
                del self.timestamps[oldest_key]
            self.cache[key] = value
            self.timestamps[key] = time.time()

        def get(self, key, default=None):
            try:
                return self[key]
            except KeyError:
                return default

        def set(self, key, value, expire=None):
            self[key] = value

        def __delitem__(self, key):
            if key in self.cache:
                del self.cache[key]
                del self.timestamps[key]

        def clear(self):
            self.cache.clear()
            self.timestamps.clear()


class CacheService(ICacheService):
    """生产级统一缓存服务，支持三级缓存、细粒度失效、穿透/击穿/雪崩防护、磁盘持久化"""

    def __init__(self):
        self.enabled = settings.rag_config["cache"]["enabled"]
        self.memory_cache = LRUCache(
            maxsize=settings.rag_config["cache"]["max_size"] or 10000
        )
        self.redis_client = None
        self._init_redis()
        self.disk_cache_enabled = getattr(settings, "rag_cache_disk_enabled", True)
        self.disk_cache_dir = self._init_disk_cache_dir()
        self.disk_cache = self._load_disk_cache()
        self.bloom_filter = None
        self.locks = {}
        self.doc_hash_map = defaultdict(set)
        self.tag_map = defaultdict(set)
        self.default_ttl = settings.rag_config["cache"]["ttl_seconds"]
        self.disk_persist_interval = getattr(
            settings, "rag_cache_disk_persist_interval", 300
        )
        self._persist_task = None
        self._start_auto_persist()

    def _init_redis(self):
        """初始化 Redis 客户端"""
        if redis_settings.cache_enabled:
            try:
                self.redis_client = RedisClient.get_client()
                logger.info("CacheService: Redis 客户端已初始化")
            except Exception as e:
                logger.warning(f"CacheService: Redis 初始化失败: {e}")
                self.redis_client = None

    def _init_disk_cache_dir(self) -> Optional[str]:
        if not self.disk_cache_enabled:
            return None

        cache_dir = getattr(settings, "rag_cache_disk_dir", None)
        if not cache_dir:
            base_dir = Path(__file__).parent.parent.parent.parent.parent
            cache_dir = str(base_dir / "app_data" / "cache")

        cache_path = Path(cache_dir)
        try:
            cache_path.mkdir(parents=True, exist_ok=True)
            logger.info(f"磁盘缓存目录已创建: {cache_dir}")
            return cache_dir
        except Exception as e:
            logger.error(f"创建磁盘缓存目录失败: {e}")
            return None

    def _load_disk_cache(self) -> dict:
        if not self.disk_cache_enabled or not self.disk_cache_dir:
            return {}

        cache_file = Path(self.disk_cache_dir) / "cache.json"
        if not cache_file.exists():
            return {}

        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            current_time = time.time()
            valid_cache = {}
            expired_count = 0

            for key, item in data.items():
                if current_time < item.get("expire_at", 0):
                    valid_cache[key] = item["value"]
                else:
                    expired_count += 1

            logger.info(
                f"从磁盘加载缓存: {len(valid_cache)} 条有效, {expired_count} 条已过期"
            )
            return valid_cache
        except Exception as e:
            logger.warning(f"加载磁盘缓存失败: {e}")
            return {}

    def _persist_cache_to_disk(self):
        if not self.disk_cache_enabled or not self.disk_cache_dir:
            return

        cache_file = Path(self.disk_cache_dir) / "cache.json"
        temp_file = cache_file.with_suffix(".tmp")

        try:
            persist_data = {}
            current_time = time.time()

            memory_cache = getattr(self.memory_cache, "cache", self.memory_cache)
            timestamps = getattr(self.memory_cache, "timestamps", {})

            for key, value in memory_cache.items():
                expire_at = current_time + self.default_ttl
                if key in timestamps:
                    expire_at = timestamps[key] + self.default_ttl

                persist_data[key] = {
                    "value": value,
                    "expire_at": expire_at,
                    "updated_at": current_time,
                }

            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(
                    persist_data,
                    f,
                    ensure_ascii=False,
                    indent=2,
                    default=lambda obj: (
                        obj.isoformat() if hasattr(obj, "isoformat") else str(obj)
                    ),
                )

            temp_file.replace(cache_file)
            logger.debug(f"缓存已持久化到磁盘: {len(persist_data)} 条")
        except Exception as e:
            logger.error(f"持久化缓存到磁盘失败: {e}")
            if temp_file.exists():
                try:
                    temp_file.unlink()
                except Exception:
                    pass

    def _start_auto_persist(self):
        if not self.disk_cache_enabled or not self.disk_cache_dir:
            return

        def persist_loop():
            while True:
                time.sleep(self.disk_persist_interval)
                try:
                    self._persist_cache_to_disk()
                except Exception as e:
                    logger.error(f"自动持久化缓存异常: {e}")

        import threading

        thread = threading.Thread(
            target=persist_loop, daemon=True, name="cache-persist"
        )
        thread.start()
        logger.info(f"缓存自动持久化已启动，间隔: {self.disk_persist_interval}秒")

    def _get_cache_key(self, key_prefix: str, args: tuple, kwargs: dict) -> str:
        key_parts = args + tuple(sorted(kwargs.items()))
        key_hash = hashlib.md5(
            json.dumps(
                key_parts,
                sort_keys=True,
                ensure_ascii=False,
                default=lambda obj: (
                    obj.isoformat() if hasattr(obj, "isoformat") else str(obj)
                ),
            ).encode()
        ).hexdigest()
        return f"rag:cache:{key_prefix}:{key_hash}"

    async def get(self, key: str, default: Any = None) -> Any:
        if not self.enabled:
            return default

        if key in self.memory_cache:
            logger.debug(f"内存缓存命中: {key}")
            return self.memory_cache[key]

        if self.disk_cache_enabled and key in self.disk_cache:
            value = self.disk_cache[key]
            self.memory_cache[key] = value
            logger.debug(f"磁盘缓存命中: {key}")
            return value

        if self.redis_client:
            try:
                redis_value = await redis_circuit_breaker.execute(
                    self.redis_client.get, key
                )
                if redis_value:
                    value = json.loads(redis_value)
                    self.memory_cache[key] = value
                    logger.debug(f"Redis缓存命中: {key}")
                    return value
            except Exception as e:
                logger.warning(f"Redis读取失败，降级: {e}")

        return default

    async def set(
        self,
        key: str,
        value: Any,
        expire: int = None,
        doc_hashes: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
        is_hot: bool = False,
    ):
        if not self.enabled:
            return

        expire = expire or self.default_ttl
        expire += int(time.time()) % 60

        self.memory_cache[key] = value

        if self.disk_cache_enabled:
            self.disk_cache[key] = value

        if self.redis_client:
            try:
                await self.redis_client.setex(
                    key,
                    expire,
                    json.dumps(
                        value,
                        ensure_ascii=False,
                        default=lambda obj: (
                            obj.isoformat() if hasattr(obj, "isoformat") else str(obj)
                        ),
                    ),
                )
                logger.debug(f"缓存已写入: {key}, TTL: {expire}s")
            except Exception as e:
                logger.warning(f"Redis写入失败: {e}")

        if doc_hashes:
            for doc_hash in doc_hashes:
                self.doc_hash_map[doc_hash].add(key)
                if self.redis_client:
                    try:
                        await self.redis_client.sadd(f"rag:doc_map:{doc_hash}", key)
                    except Exception:
                        pass

        if tags:
            for tag in tags:
                self.tag_map[tag].add(key)
                if self.redis_client:
                    try:
                        await self.redis_client.sadd(f"rag:tag_map:{tag}", key)
                    except Exception:
                        pass

    async def set_with_jitter(
        self, key: str, value: Any, base_ttl: int = None, tags: list[str] = None
    ) -> None:
        base_ttl = base_ttl or self.default_ttl
        jitter = int(base_ttl * 0.2)
        actual_ttl = base_ttl + random.randint(-jitter, jitter)
        actual_ttl = max(60, actual_ttl)
        await self.set(key, value, expire=actual_ttl, tags=tags)

    async def delete(self, key: str) -> None:
        if key in self.memory_cache:
            del self.memory_cache[key]

        if self.disk_cache_enabled and key in self.disk_cache:
            del self.disk_cache[key]

        if self.redis_client:
            try:
                await self.redis_client.delete(key)
                logger.debug(f"缓存已删除: {key}")
            except Exception as e:
                logger.warning(f"Redis删除失败: {e}")

    async def invalidate_tag(self, tag: str) -> None:
        if tag not in self.tag_map:
            return

        keys = self.tag_map[tag]
        if not keys:
            return

        for key in keys:
            if key in self.memory_cache:
                del self.memory_cache[key]

        if self.redis_client:
            try:
                await self.redis_client.delete(*keys)
                logger.debug(f"标签 {tag} 关联的 {len(keys)} 个缓存已失效")
            except Exception as e:
                logger.warning(f"Redis批量删除失败: {e}")

        del self.tag_map[tag]

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
        if self.redis_client:
            acquired = await self.redis_client.set(lock_key, "1", nx=True, ex=10)
        else:
            acquired = True

        if acquired:
            try:
                result = await mysql_circuit_breaker.execute(query_func)
                if result is None:
                    await self.set(key, "__NULL__", expire=300)
                else:
                    await self.set_with_jitter(
                        key, result, base_ttl=ttl or self.default_ttl
                    )
                return result
            finally:
                if self.redis_client:
                    await self.redis_client.delete(lock_key)
        else:
            await asyncio.sleep(0.1)
            return await self.get_with_lock(key, query_func, ttl)

    async def get_with_logical_expiry(
        self, key: str, query_func, physical_ttl: int = 86400
    ) -> Any:
        cached = await self.get(key)
        if cached:
            if isinstance(cached, dict) and "logical_expire" in cached:
                if time.time() < cached.get("logical_expire", 0):
                    return cached["value"]
                else:
                    asyncio.create_task(
                        self._refresh_cache(key, query_func, physical_ttl)
                    )
                    return cached["value"]

        return await self._refresh_cache(key, query_func, physical_ttl)

    async def _refresh_cache(self, key: str, query_func, physical_ttl: int) -> Any:
        result = await mysql_circuit_breaker.execute(query_func)
        data = {
            "value": result,
            "logical_expire": time.time() + self.default_ttl,
        }
        await self.set(key, data, expire=physical_ttl)
        return result

    async def invalidate_by_doc_hash(self, doc_hash: str):
        if not self.enabled:
            return

        keys_to_remove = self.doc_hash_map.pop(doc_hash, set())
        if self.redis_client:
            try:
                redis_keys = await self.redis_client.smembers(f"rag:doc_map:{doc_hash}")
                keys_to_remove.update(redis_keys)
                await self.redis_client.delete(f"rag:doc_map:{doc_hash}")
            except Exception as e:
                logger.warning(f"Redis doc map get failed: {e}")

        for key in keys_to_remove:
            if key in self.memory_cache:
                del self.memory_cache[key]
            if self.redis_client:
                try:
                    await self.redis_client.delete(key)
                except Exception:
                    pass

        logger.info(
            f"Invalidated {len(keys_to_remove)} cache entries for doc hash {doc_hash}"
        )

    async def invalidate_by_tag(self, tag: str):
        if not self.enabled:
            return

        keys_to_remove = self.tag_map.pop(tag, set())
        if self.redis_client:
            try:
                redis_keys = await self.redis_client.smembers(f"rag:tag_map:{tag}")
                keys_to_remove.update(redis_keys)
                await self.redis_client.delete(f"rag:tag_map:{tag}")
            except Exception as e:
                logger.warning(f"Redis tag map get failed: {e}")

        for key in keys_to_remove:
            if key in self.memory_cache:
                del self.memory_cache[key]
            if self.redis_client:
                try:
                    await self.redis_client.delete(key)
                except Exception:
                    pass

    async def clear_all(self) -> None:
        self.memory_cache.clear()
        if self.disk_cache_enabled:
            self.disk_cache.clear()
        try:
            if self.redis_client:
                await self.redis_client.flushdb()
            logger.info("所有缓存已清空")
        except Exception as e:
            logger.warning(f"Redis清空失败: {e}")

    def clear(self):
        self.memory_cache.clear()
        self.doc_hash_map.clear()
        self.tag_map.clear()
        self.locks.clear()

        if self.disk_cache_enabled:
            self.disk_cache.clear()
            self._persist_cache_to_disk()

        logger.info("All cache cleared")

    def get_cache_stats(self) -> dict:
        return {
            "enabled": self.enabled,
            "memory_cache_size": len(
                getattr(self.memory_cache, "cache", self.memory_cache)
            ),
            "disk_cache_size": len(self.disk_cache) if self.disk_cache_enabled else 0,
            "disk_cache_enabled": self.disk_cache_enabled,
            "disk_cache_dir": self.disk_cache_dir,
            "max_size": settings.rag_config["cache"]["max_size"],
            "default_ttl": self.default_ttl,
            "redis_enabled": self.redis_client is not None,
            "bloom_filter_enabled": self.bloom_filter is not None,
            "doc_hash_count": len(self.doc_hash_map),
            "tag_count": len(self.tag_map),
        }


def cached(
    expire: int = None,
    key_prefix: str = "",
    doc_hash_param: Optional[str] = None,
    tags: Optional[List[str]] = None,
    is_hot: bool = False,
):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            from src.service.cache_service import cache_service

            cache_key = cache_service._get_cache_key(key_prefix, args, kwargs)

            doc_hashes = None
            if doc_hash_param and doc_hash_param in kwargs:
                doc_hashes = [kwargs[doc_hash_param]]

            async def load_func():
                return await func(*args, **kwargs)

            return await cache_service.get_with_protection(
                cache_key,
                load_func,
                expire=expire,
                doc_hashes=doc_hashes,
                tags=tags,
                is_hot=is_hot,
            )

        return wrapper

    return decorator


cache_service = CacheService()
