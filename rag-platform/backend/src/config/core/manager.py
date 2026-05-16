"""配置管理器

从 backend/ 继承，rag-platform 中提供简化版实现。
完整的配置管理使用 MySQL + Redis Pub/Sub 热重载。
"""
from typing import Any, Optional


class ConfigManager:
    """配置管理器

    简化版实现，提供与 backend/ 兼容的接口。
    完整版需配合 ConfigCache + Redis Pub/Sub 热重载使用。
    """

    def __init__(self):
        self._config: dict[str, Any] = {}

    def get(self, key: str, default: Any = None) -> Any:
        """获取配置项"""
        return self._config.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """设置配置项"""
        self._config[key] = value

    def get_all(self) -> dict[str, Any]:
        """获取全部配置"""
        return dict(self._config)

    def load_from_dict(self, data: dict[str, Any]) -> None:
        """从字典加载配置"""
        self._config.update(data)

    def get_latest_config(self) -> Optional[dict[str, Any]]:
        """获取最新配置快照"""
        return dict(self._config) if self._config else None
