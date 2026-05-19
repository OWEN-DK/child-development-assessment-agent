"""配置管理器

负责配置的版本化存储、变更事件发布和与 Settings 的同步。
"""
from typing import Any, Dict, List, Optional

from src.config.core.events import ConfigChangedEvent
from src.core.event_bus import event_bus


def _get_logger():
    """延迟导入 logger 避免循环引用"""
    from src.utils.logger import logger
    return logger


class ConfigManager:
    """配置管理器

    从 Settings 提取配置快照，提供与 LLM/Embedding/Reranker 工厂兼容的接口。
    支持从字典加载配置并发布变更事件以触发热重载。
    """

    def __init__(self):
        self._config: Dict[str, Any] = {}
        self._version_id: Optional[str] = None

    def get(self, key: str, default: Any = None) -> Any:
        """获取单个配置项"""
        return self._config.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """设置单个配置项（不触发事件）"""
        self._config[key] = value

    def get_all(self) -> Dict[str, Any]:
        """获取全部配置"""
        return dict(self._config)

    def get_full_config(self) -> Dict[str, Any]:
        """获取完整配置字典（工厂接口）"""
        if not self._config:
            self.sync_from_settings()
        return dict(self._config)

    def get_latest_config(self) -> Optional[Dict[str, Any]]:
        """获取最新配置快照"""
        return dict(self._config) if self._config else None

    def load_from_dict(self, data: Dict[str, Any]) -> None:
        """从字典加载配置并发布变更事件"""
        changed_keys = self._detect_changes(data)
        self._config.update(data)
        if changed_keys:
            _get_logger().info("配置变更: %d 项", len(changed_keys))
            event_bus.publish(
                ConfigChangedEvent(
                    config_key=",".join(changed_keys),
                    changed_keys=changed_keys,
                )
            )

    def sync_from_settings(self, settings: Optional["Settings"] = None) -> None:  # noqa: F821
        """从 Settings 对象同步配置快照"""
        if settings is None:
            from src.config import settings as app_settings

            settings = app_settings

        flat_config = self._extract_config_from_settings(settings)
        changed_keys = self._detect_changes(flat_config)
        self._config.update(flat_config)
        if changed_keys:
            _get_logger().debug("从 Settings 同步: %d 项变更", len(changed_keys))

    def _extract_config_from_settings(self, settings: "Settings") -> Dict[str, Any]:  # noqa: F821
        """从 Settings 对象提取扁平化配置字典"""
        config = {}

        flat = settings.model_dump(exclude_none=False)

        # 展平 llm_scene_configs 为 llm_{scene} 条目（工厂期望的格式）
        for key, value in flat.items():
            config[key] = value

        if hasattr(settings, "llm_scene_configs"):
            scene_configs = settings.llm_scene_configs
            for scene_name, scene_config in scene_configs.items():
                config[f"llm_{scene_name}"] = (
                    scene_config.model_dump() if hasattr(scene_config, "model_dump") else scene_config
                )

        return config

    def _detect_changes(self, new_data: Dict[str, Any]) -> List[str]:
        """检测变更的键列表"""
        changed = []
        for key, value in new_data.items():
            old_value = self._config.get(key)
            if old_value != value:
                changed.append(key)
        return changed


config_manager = ConfigManager()
