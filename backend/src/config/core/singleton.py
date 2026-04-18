"""配置单例管理

提供全局配置实例的获取和重载功能。
"""

import logging
from threading import RLock
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.config import Settings

_settings_instance = None
_lock = RLock()
_logger = logging.getLogger(__name__)


def get_settings() -> "Settings":
    """获取配置单例"""
    global _settings_instance
    if _settings_instance is None:
        with _lock:
            if _settings_instance is None:
                from src.config import Settings

                _settings_instance = Settings()
    return _settings_instance


def reload_settings() -> "Settings":
    """重新加载配置并返回新的Settings实例

    实现失败回退机制：重载失败时返回原有配置实例
    """
    global _settings_instance
    with _lock:
        try:
            from src.config import Settings, compare_config_changes

            new_settings = Settings()
            new_settings.model_validate(new_settings.model_dump())
            old_settings = _settings_instance
            _settings_instance = new_settings
            _logger.info("配置重载成功")

            if old_settings:
                changed_fields = compare_config_changes(old_settings, new_settings)
                if changed_fields:
                    _logger.info(f"配置变更字段: {list(changed_fields.keys())}")

            from src.config.core.manager import config_manager

            config_manager.sync_cache_from_settings(new_settings)

            return new_settings
        except Exception as e:
            _logger.error(f"配置重载失败，保留原有配置: {e}")
            from src.config import Settings

            return _settings_instance if _settings_instance else Settings()
