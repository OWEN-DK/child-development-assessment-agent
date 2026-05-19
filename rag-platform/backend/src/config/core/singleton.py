"""Settings 单例管理

提供线程安全的 Settings 实例获取与热重载。
"""
import logging
from threading import RLock
from typing import Optional

logger = logging.getLogger(__name__)

_settings_instance: Optional["Settings"] = None  # noqa: F821
_settings_lock = RLock()


def get_settings() -> "Settings":  # noqa: F821
    """获取 Settings 单例（双重检查锁定）"""
    global _settings_instance
    if _settings_instance is None:
        with _settings_lock:
            if _settings_instance is None:
                from src.config import Settings

                _settings_instance = Settings()
                logger.info("Settings 单例已初始化")
    return _settings_instance


def reload_settings() -> "Settings":  # noqa: F821
    """热重载 Settings（重建实例，保留旧实例用于比较）"""
    global _settings_instance
    import src.config
    from src.config import Settings, compare_config_changes

    with _settings_lock:
        old_settings = _settings_instance
        new_settings = Settings()
        if old_settings is not None:
            changes = compare_config_changes(old_settings, new_settings)
            if changes:
                logger.info("配置变更: %d 项", len(changes))
        _settings_instance = new_settings
        src.config.settings = new_settings
        logger.info("Settings 已热重载")
        return _settings_instance
