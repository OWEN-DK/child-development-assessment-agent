import json
import time
from typing import Any, List, Optional

from src.config import redis_settings, settings
from src.core.circuit_breaker import redis_circuit_breaker
from src.utils.logger import logger


class RedisCache:
    _redis_ever_initialized = False

    def __init__(self):
        self.redis_client = None
        self._init_redis()

    def _init_redis(self):
        if redis_settings.cache_enabled:
            try:
                from src.core.redis_client import RedisClient
                self.redis_client = RedisClient.get_client()
                if not RedisCache._redis_ever_initialized:
                    RedisCache._redis_ever_initialized = True
                    logger.info("CacheService: Redis 客户端已初始化")
            except Exception as e:
                logger.warning(f"CacheService: Redis 初始化失败: {e}")
                self.redis_client = None

    async def get(self, key: str) -> Optional[str]:
        if not self.redis_client:
            return None
        try:
            redis_value = await redis_circuit_breaker.execute(self.redis_client.get, key)
            if redis_value:
                return redis_value
        except Exception as e:
            logger.warning(f"Redis读取失败，降级: {e}")
        return None

    async def set(self, key: str, value: str, expire: int):
        if not self.redis_client:
            return
        try:
            await self.redis_client.setex(key, expire, value)
            logger.debug(f"缓存已写入: {key}, TTL: {expire}s")
        except (ConnectionError, TimeoutError, ConnectionResetError) as e:
            logger.warning(f"Redis连接异常，重置客户端: {e}")
            self.redis_client = None
        except Exception as e:
            logger.warning(f"Redis写入失败: {e}")

    async def delete(self, key: str):
        if not self.redis_client:
            return
        try:
            await self.redis_client.delete(key)
            logger.debug(f"缓存已删除: {key}")
        except Exception as e:
            logger.warning(f"Redis删除失败: {e}")

    async def delete_many(self, *keys):
        if not self.redis_client:
            return
        try:
            await self.redis_client.delete(*keys)
        except Exception as e:
            logger.warning(f"Redis批量删除失败: {e}")

    async def sadd(self, key: str, *values):
        if not self.redis_client:
            return
        try:
            await self.redis_client.sadd(key, *values)
        except Exception:
            pass

    async def smembers(self, key: str) -> set:
        if not self.redis_client:
            return set()
        try:
            return await self.redis_client.smembers(key)
        except Exception as e:
            logger.warning(f"Redis doc map get failed: {e}")
            return set()

    async def flushdb(self):
        if not self.redis_client:
            return
        try:
            await self.redis_client.flushdb()
        except Exception as e:
            logger.warning(f"Redis清空失败: {e}")

    async def set_lock(self, lock_key: str, value: str, ex: int) -> bool:
        if not self.redis_client:
            return True
        try:
            acquired = await self.redis_client.set(lock_key, value, nx=True, ex=ex)
            return acquired
        except Exception:
            return True

    async def delete_lock(self, lock_key: str):
        if not self.redis_client:
            return
        try:
            await self.redis_client.delete(lock_key)
        except Exception:
            pass
