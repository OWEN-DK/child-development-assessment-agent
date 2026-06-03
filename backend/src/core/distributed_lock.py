import asyncio

from src.config import redis_settings
from src.core.redis_client import RedisClient
from src.utils.logger import logger

# 本地锁降级（Redis 不可用时使用）
_local_locks: dict[str, asyncio.Lock] = {}


class DistributedLock:
    """基于 Redis 的分布式锁服务，Redis 不可用时降级为本地 asyncio.Lock"""

    @classmethod
    async def _watchdog(cls, lock, timeout: int, stop_event: asyncio.Event):
        """锁自动续期看门狗（仅 Redis 模式）"""
        renewal_interval = timeout / 3.0
        while not stop_event.is_set():
            await asyncio.sleep(renewal_interval)
            if not stop_event.is_set():
                try:
                    await lock.extend(timeout)
                except Exception as e:
                    logger.warning(f"分布式锁续期失败: {e}")
                    break

    @classmethod
    async def execute_with_lock(
        cls, lock_name: str, func, timeout: int = None, *args, **kwargs
    ):
        """使用分布式锁包装函数执行。

        Redis 不可用时自动降级为本地 asyncio.Lock（单实例安全）。
        """
        timeout = timeout or redis_settings.lock_timeout

        try:
            redis_client = RedisClient.get_client()
            lock = redis_client.lock(
                f"child-dev:lock:{lock_name}", timeout=timeout, blocking_timeout=5
            )
            async with lock:
                stop_event = asyncio.Event()
                watchdog_task = asyncio.create_task(
                    cls._watchdog(lock, timeout, stop_event)
                )
                try:
                    return await func(*args, **kwargs)
                finally:
                    stop_event.set()
                    watchdog_task.cancel()
        except Exception as e:
            # Redis 不可用或锁获取失败，降级到本地锁
            logger.warning(f"Redis 分布式锁失败，降级为本地锁 ({lock_name}): {e}")
            if lock_name not in _local_locks:
                _local_locks[lock_name] = asyncio.Lock()
            async with _local_locks[lock_name]:
                return await func(*args, **kwargs)
