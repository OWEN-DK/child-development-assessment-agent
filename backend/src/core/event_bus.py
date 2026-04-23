import asyncio
import json
import time
import uuid
from collections import defaultdict
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Type

from src.core.events import BaseEvent

if TYPE_CHECKING:
    from redis.asyncio.client import PubSub


def _get_logger():
    """延迟导入 logger，避免循环导入"""
    from src.utils.logger import logger
    return logger

if TYPE_CHECKING:
    from redis.asyncio.client import PubSub

try:
    import redis.asyncio as redis

    REDIS_AVAILABLE = True
except ImportError:
    redis = None
    REDIS_AVAILABLE = False


class IndexUpdateEvent(BaseEvent):
    """索引更新事件"""

    def __init__(self, index_id: str = None):
        super().__init__()
        self.index_id = index_id


class ConfigVersionCreatedEvent(BaseEvent):
    """配置版本创建事件"""

    def __init__(self, version_id: str = None):
        super().__init__()
        self.version_id = version_id


# 统一使用 config/core/events.py 中的完整版本
# 注意：不在此处直接导入，避免循环导入。订阅者应直接从 src.config.core.events 导入。

def _get_event_classes():
    """延迟获取事件类，避免循环导入"""
    from src.config.core.events import (
        ConfigChangedEvent,
        ConfigFactoryResetEvent,
        ConfigResetEvent,
        ConfigRollbackEvent,
    )
    return {
        "ConfigChangedEvent": ConfigChangedEvent,
        "ConfigVersionCreatedEvent": ConfigVersionCreatedEvent,
        "ConfigRollbackEvent": ConfigRollbackEvent,
        "ConfigFactoryResetEvent": ConfigFactoryResetEvent,
        "ConfigResetEvent": ConfigResetEvent,
    }


class EventBus:
    """事件总线，支持内存事件 + Redis Pub/Sub跨实例传播"""

    _instance_id: str = str(uuid.uuid4())
    _subscribers: Dict[Type[BaseEvent], List[Callable[[Any], None]]] = defaultdict(list)
    _redis_subscriber: "PubSub | None" = None

    @classmethod
    def subscribe(
        cls, event_type: Type[BaseEvent], callback: Callable[[Any], None]
    ) -> None:
        """订阅事件（内存，建议使用weakref或显式unsubscribe防止内存泄漏）"""
        cls._subscribers[event_type].append(callback)
        _get_logger().debug(f"Subscribed to event: {event_type.__name__}")

    @classmethod
    def unsubscribe(
        cls, event_type: Type[BaseEvent], callback: Callable[[Any], None]
    ) -> None:
        """显式取消订阅，防止Controller等短生命周期对象内存泄漏"""
        if callback in cls._subscribers[event_type]:
            cls._subscribers[event_type].remove(callback)

    @classmethod
    def publish(cls, event: BaseEvent) -> None:
        """发布事件（内存 + Redis Pub/Sub）"""
        event_type = type(event)
        for callback in cls._subscribers.get(event_type, []):
            try:
                callback(event)
            except Exception as e:
                _get_logger().error(f"Event callback failed for {event_type.__name__}: {e}")

        if REDIS_AVAILABLE:
            try:
                from src.config import redis_settings
                from src.core.redis_client import RedisClient

                if not redis_settings.pubsub_enabled:
                    return

                event_data = (
                    event.model_dump()
                    if hasattr(event, "model_dump")
                    else event.__dict__
                )

                payload = {
                    "publisher_id": cls._instance_id,
                    "event_type": event_type.__name__,
                    "event_data": event_data,
                }
                coro = RedisClient.get_client().publish(
                    f"child-dev:events:{event_type.__name__}",
                    json.dumps(payload, ensure_ascii=False),
                )
                try:
                    loop = asyncio.get_running_loop()
                    loop.create_task(coro)
                except RuntimeError:
                    asyncio.run(coro)
            except Exception as e:
                _get_logger().warning(f"Redis Pub/Sub 消息发布失败: {e}")

    @classmethod
    async def start_redis_subscriber(cls):
        """启动Redis Pub/Sub订阅器（接收其他实例的事件）"""
        if not REDIS_AVAILABLE:
            _get_logger().info("Redis Pub/Sub 已禁用，跳过订阅器启动")
            return

        try:
            from src.config import redis_settings
            from src.core.redis_client import RedisClient

            if not redis_settings.pubsub_enabled:
                _get_logger().info("Redis Pub/Sub 已禁用，跳过订阅器启动")
                return

            cls._redis_subscriber = RedisClient.get_client().pubsub()
            await cls._redis_subscriber.psubscribe("child-dev:events:*")
            _get_logger().info("Redis Pub/Sub 订阅器已启动")

            async for message in cls._redis_subscriber.listen():
                if message["type"] == "pmessage":
                    try:
                        payload = json.loads(message["data"])
                        if payload.get("publisher_id") == cls._instance_id:
                            continue

                        event_type_name = payload.get("event_type")
                        event_data = payload.get("event_data", {})

                        event_type = _get_event_classes().get(event_type_name)
                        if not event_type:
                            _get_logger().warning(f"未知事件类型: {event_type_name}")
                            continue

                        event = event_type(**event_data)
                        for callback in cls._subscribers.get(event_type, []):
                            try:
                                callback(event)
                            except Exception as e:
                                _get_logger().error(f"跨实例事件回调执行失败: {e}")

                    except Exception as e:
                        _get_logger().error(f"Redis Pub/Sub 消息处理失败: {e}")

        except Exception as e:
            _get_logger().error(f"Redis Pub/Sub 订阅器启动失败: {e}")

    @classmethod
    async def stop_redis_subscriber(cls):
        """停止Redis订阅器"""
        if cls._redis_subscriber:
            await cls._redis_subscriber.close()
            cls._redis_subscriber = None
            _get_logger().info("Redis Pub/Sub 订阅器已停止")


event_bus = EventBus()
