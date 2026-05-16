"""事件总线

简化版实现，支持内存事件订阅与发布。
从 backend/ 继承，rag-platform 中去除了 Redis Pub/Sub 跨实例传播。
"""
from collections import defaultdict
from typing import Any, Callable

from src.core.events import BaseEvent
from src.utils.logger import logger


class EventBus:
    """事件总线（内存模式，无 Redis 跨实例传播）"""

    _subscribers: dict[type[BaseEvent], list[Callable[[Any], None]]] = defaultdict(list)

    @classmethod
    def subscribe(cls, event_type: type[BaseEvent], callback: Callable[[Any], None]) -> None:
        """订阅事件"""
        cls._subscribers[event_type].append(callback)

    @classmethod
    def unsubscribe(cls, event_type: type[BaseEvent], callback: Callable[[Any], None]) -> None:
        """取消订阅"""
        if callback in cls._subscribers[event_type]:
            cls._subscribers[event_type].remove(callback)

    @classmethod
    def publish(cls, event: BaseEvent) -> None:
        """发布事件到所有订阅者"""
        event_type = type(event)
        for callback in cls._subscribers.get(event_type, []):
            try:
                callback(event)
            except Exception as e:
                logger.error(f"事件回调失败 ({event_type.__name__}): {e}")


event_bus = EventBus()
