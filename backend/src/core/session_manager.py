import json
import time
from typing import Any

from src.config import redis_settings
from src.core.redis_client import RedisClient
from src.utils.logger import logger


class SessionManager:
    """基于 Redis 的会话管理器，Redis 不可用时自动降级到内存存储"""

    _memory_store: dict[str, dict[str, Any]] = {}
    _memory_ttl: dict[str, float] = {}

    @classmethod
    def _get_redis(cls):
        """获取 Redis 客户端，失败返回 None"""
        try:
            return RedisClient.get_client()
        except Exception:
            return None

    @classmethod
    async def save_session(cls, session_id: str, data: dict, ttl: int = None) -> None:
        """保存会话（优先 Redis，降级内存）"""
        ttl = ttl or redis_settings.session_ttl
        redis_client = cls._get_redis()
        if redis_client:
            try:
                pipe = redis_client.pipeline()
                for key, value in data.items():
                    pipe.hset(
                        f"child-dev:session:{session_id}",
                        key,
                        json.dumps(value, ensure_ascii=False),
                    )
                pipe.expire(f"child-dev:session:{session_id}", ttl)
                await pipe.execute()
                logger.debug(f"会话已保存到 Redis: {session_id}")
                return
            except Exception as e:
                logger.warning(f"Redis 保存会话失败，降级到内存: {e}")

        # 内存兜底
        cls._memory_store[session_id] = {k: json.dumps(v, ensure_ascii=False) for k, v in data.items()}
        cls._memory_ttl[session_id] = time.time() + ttl
        logger.debug(f"会话已保存到内存: {session_id}")

    @classmethod
    async def load_session(cls, session_id: str) -> dict | None:
        """加载会话（优先 Redis，降级内存）"""
        redis_client = cls._get_redis()
        if redis_client:
            try:
                session_data = await redis_client.hgetall(f"child-dev:session:{session_id}")
                if session_data:
                    result = {}
                    for key, value in session_data.items():
                        try:
                            result[key] = json.loads(value)
                        except json.JSONDecodeError:
                            result[key] = value
                    return result
            except Exception as e:
                logger.warning(f"Redis 加载会话失败，降级到内存: {e}")

        # 内存兜底
        raw = cls._memory_store.get(session_id)
        if raw and time.time() < cls._memory_ttl.get(session_id, 0):
            result = {}
            for key, value in raw.items():
                try:
                    result[key] = json.loads(value)
                except json.JSONDecodeError:
                    result[key] = value
            return result
        # 过期清理
        if raw:
            cls._memory_store.pop(session_id, None)
            cls._memory_ttl.pop(session_id, None)
        return None

    @classmethod
    async def update_session_field(
        cls, session_id: str, field: str, value: any, ttl: int = None
    ) -> None:
        """更新会话单个字段"""
        redis_client = cls._get_redis()
        if redis_client:
            try:
                await redis_client.hset(
                    f"child-dev:session:{session_id}",
                    field,
                    json.dumps(value, ensure_ascii=False),
                )
                if ttl:
                    await redis_client.expire(f"child-dev:session:{session_id}", ttl)
                return
            except Exception as e:
                logger.warning(f"Redis 更新会话字段失败，降级到内存: {e}")

        # 内存兜底
        if session_id not in cls._memory_store:
            cls._memory_store[session_id] = {}
            cls._memory_ttl[session_id] = time.time() + (ttl or redis_settings.session_ttl)
        cls._memory_store[session_id][field] = json.dumps(value, ensure_ascii=False)
        if ttl:
            cls._memory_ttl[session_id] = time.time() + ttl

    @classmethod
    async def delete_session(cls, session_id: str) -> None:
        """删除会话"""
        redis_client = cls._get_redis()
        if redis_client:
            try:
                await redis_client.delete(f"child-dev:session:{session_id}")
            except Exception as e:
                logger.warning(f"Redis 删除会话失败: {e}")
        # 始终清理内存
        cls._memory_store.pop(session_id, None)
        cls._memory_ttl.pop(session_id, None)
        logger.debug(f"会话已删除: {session_id}")
