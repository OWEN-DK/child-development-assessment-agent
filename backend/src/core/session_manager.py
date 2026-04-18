import json

from src.config import redis_settings
from src.core.redis_client import RedisClient
from src.utils.logger import logger


class SessionManager:
    """基于 Redis 的会话管理器"""

    @classmethod
    async def save_session(cls, session_id: str, data: dict, ttl: int = None) -> None:
        """保存会话到 Redis Hash"""
        ttl = ttl or redis_settings.session_ttl
        redis_client = RedisClient.get_client()
        pipe = redis_client.pipeline()
        for key, value in data.items():
            pipe.hset(
                f"child-dev:session:{session_id}",
                key,
                json.dumps(value, ensure_ascii=False),
            )
        pipe.expire(f"child-dev:session:{session_id}", ttl)
        await pipe.execute()
        logger.debug(f"会话已保存: {session_id}")

    @classmethod
    async def load_session(cls, session_id: str) -> dict | None:
        """从 Redis Hash 加载会话"""
        redis_client = RedisClient.get_client()
        session_data = await redis_client.hgetall(f"child-dev:session:{session_id}")
        if not session_data:
            return None

        result = {}
        for key, value in session_data.items():
            try:
                result[key] = json.loads(value)
            except json.JSONDecodeError:
                result[key] = value
        return result

    @classmethod
    async def update_session_field(
        cls, session_id: str, field: str, value: any, ttl: int = None
    ) -> None:
        """更新会话单个字段"""
        redis_client = RedisClient.get_client()
        await redis_client.hset(
            f"child-dev:session:{session_id}",
            field,
            json.dumps(value, ensure_ascii=False),
        )
        if ttl:
            await redis_client.expire(f"child-dev:session:{session_id}", ttl)

    @classmethod
    async def delete_session(cls, session_id: str) -> None:
        """删除会话"""
        await RedisClient.get_client().delete(f"child-dev:session:{session_id}")
        logger.debug(f"会话已删除: {session_id}")
