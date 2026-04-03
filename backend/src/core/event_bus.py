import time
from collections import defaultdict
from typing import Type, Dict, List, Callable, Any
from src.utils.logger import logger

class BaseEvent:
    """事件基类"""
    def __init__(self):
        self.timestamp = time.time()

class IndexUpdateEvent(BaseEvent):
    """索引更新事件"""
    def __init__(self, index_id: str = None):
        super().__init__()
        self.index_id = index_id

class EventBus:
    """事件总线，实现组件解耦"""
    _subscribers: Dict[Type[BaseEvent], List[Callable[[Any], None]]] = defaultdict(list)
    
    @classmethod
    def subscribe(cls, event_type: Type[BaseEvent], callback: Callable[[Any], None]) -> None:
        """订阅事件"""
        cls._subscribers[event_type].append(callback)
        logger.debug(f"Subscribed to event: {event_type.__name__}")
    
    @classmethod
    def publish(cls, event: BaseEvent) -> None:
        """发布事件"""
        event_type = type(event)
        logger.debug(f"Publishing event: {event_type.__name__}")
        
        for callback in cls._subscribers.get(event_type, []):
            try:
                callback(event)
            except Exception as e:
                logger.error(f"Event callback failed for {event_type.__name__}: {e}")

# 全局事件总线实例
event_bus = EventBus()
