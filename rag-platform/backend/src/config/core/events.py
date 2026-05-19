"""配置变更事件类型

从 backend/ 继承，rag-platform 中提供基础事件类型定义。
完整的事件总线实现在 core/event_bus.py 中。
"""
from src.core.events import BaseEvent


class ConfigChangedEvent(BaseEvent):
    """配置变更事件"""
    def __init__(self, config_key: str = "", old_value=None, new_value=None, changed_keys=None):
        super().__init__()
        self.config_key = config_key
        self.old_value = old_value
        self.new_value = new_value
        self.changed_keys = changed_keys or ([config_key] if config_key else [])


class ConfigRollbackEvent(BaseEvent):
    """配置回滚事件"""
    def __init__(self, version_id: str = ""):
        super().__init__()
        self.version_id = version_id


class ConfigResetEvent(BaseEvent):
    """配置重置事件"""
    pass


class ConfigFactoryResetEvent(BaseEvent):
    """工厂重置事件"""
    pass
