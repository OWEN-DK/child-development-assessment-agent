"""Redis 异步客户端单例

从 .env 读取 REDIS_URL，提供全局 Redis 客户端。
"""
import redis.asyncio as redis
from redis.asyncio import ConnectionPool
from redis.backoff import ExponentialBackoff
from redis.exceptions import BusyLoadingError, ConnectionError, TimeoutError
from redis.retry import Retry

from src.utils.logger import logger


class RedisClient:
    """Redis 异步客户端单例"""

    _instance: redis.Redis | None = None
    _pool: ConnectionPool | None = None

    @classmethod
    def get_client(cls) -> redis.Redis:
        """获取 Redis 客户端实例（懒加载）"""
        if cls._instance is not None:
            return cls._instance

        from src.config import settings

        retry = Retry(
            backoff=ExponentialBackoff(cap=3, base=0.5),
            retries=5,
            supported_errors=(
                ConnectionError,
                TimeoutError,
                BusyLoadingError,
                ConnectionResetError,
            ),
        )
        cls._pool = ConnectionPool.from_url(
            settings.redis_url,
            max_connections=10,
            socket_timeout=5,
            socket_connect_timeout=5,
            decode_responses=True,
            retry=retry,
            retry_on_timeout=True,
            health_check_interval=30,
        )
        cls._instance = redis.Redis(connection_pool=cls._pool)
        logger.info("Redis 客户端已初始化")
        return cls._instance

    @classmethod
    async def close(cls):
        """关闭 Redis 连接池"""
        if cls._pool:
            await cls._pool.disconnect()
            logger.info("Redis 连接池已关闭")
