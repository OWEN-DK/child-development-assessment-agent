from typing import Any, Dict

from src.core.events import BaseEvent


class ConfigChangedEvent(BaseEvent):
    def __init__(
        self,
        from_version: str,
        to_version: str,
        changed_keys: list[str],
        config_snapshot: Dict[str, Any]
    ):
        super().__init__()
        self.from_version = from_version
        self.to_version = to_version
        self.changed_keys = changed_keys
        self.config_snapshot = config_snapshot


class ConfigRollbackEvent(BaseEvent):
    def __init__(
        self,
        from_version: str,
        to_version: str,
        rollback_at: str
    ):
        super().__init__()
        self.from_version = from_version
        self.to_version = to_version
        self.rollback_at = rollback_at


class ConfigResetEvent(BaseEvent):
    def __init__(
        self,
        from_version: str,
        reset_at: str
    ):
        super().__init__()
        self.from_version = from_version
        self.reset_at = reset_at


class ConfigFactoryResetEvent(BaseEvent):
    """配置工厂重置事件"""

    def __init__(self, version_id: str = None):
        super().__init__()
        self.version_id = version_id
