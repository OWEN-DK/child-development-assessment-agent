import asyncio

from redis.exceptions import LockError

from src.config import redis_settings
from src.core.redis_client import RedisClient
from src.utils.logger import logger


class DistributedLock:
    """基于 Redis 的分布式锁服务"""

    @classmethod
    async def _watchdog(cls, lock, timeout: int, stop_event: asyncio.Event):
        """锁自动续期看门狗"""
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
        """使用 redis 内置的健壮分布式锁包装器，并带有看门狗续期机制"""
        timeout = timeout or redis_settings.lock_timeout
        redis_client = RedisClient.get_client()
        lock = redis_client.lock(
            f"child-dev:lock:{lock_name}", timeout=timeout, blocking_timeout=5
        )
        try:
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
        except LockError:
            logger.error(f"无法获取分布式锁: {lock_name}")
            raise RuntimeError(f"无法获取分布式锁: {lock_name}")
