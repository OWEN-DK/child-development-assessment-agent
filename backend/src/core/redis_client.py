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
    _loop_id: int | None = None

    @classmethod
    def get_client(cls) -> redis.Redis:
        """获取 Redis 客户端实例（懒加载）"""
        import asyncio
        from src.config import redis_settings
        
        current_loop = asyncio.get_event_loop()
        current_loop_id = id(current_loop)
        
        # 如果实例不存在，或者当前循环与创建时的循环不同，重新初始化
        if cls._instance is None or cls._loop_id != current_loop_id:
            # 如果已有旧连接池，先关闭
            if cls._pool:
                asyncio.create_task(cls._pool.disconnect())
            
            # 配置重试策略：指数退避，最多重试5次
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
                redis_settings.redis_url,
                password=redis_settings.redis_password or None,
                max_connections=redis_settings.redis_max_connections,
                socket_timeout=redis_settings.redis_socket_timeout,
                socket_connect_timeout=redis_settings.redis_socket_connect_timeout,
                decode_responses=True,
                retry=retry,
                retry_on_timeout=True,
                health_check_interval=120,  # 每120秒做一次连接健康检查
            )
            cls._instance = redis.Redis(connection_pool=cls._pool)
            cls._loop_id = current_loop_id
            logger.info(f"Redis 客户端已初始化，已配置自动重试和健康检查，Loop ID: {current_loop_id}")
        return cls._instance

    @classmethod
    async def close(cls):
        """关闭 Redis 连接池"""
        if cls._pool:
            await cls._pool.disconnect()
            logger.info("Redis 连接池已关闭")
