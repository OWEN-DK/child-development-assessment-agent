"""配置读取辅助函数

提供从配置中心读取校验相关配置的便捷方法。
"""

from typing import Any

from src.config import config_manager


async def get_config_value(key: str, default: Any = None) -> Any:
    """从配置中心读取配置值

    Args:
        key: 配置键名
        default: 默认值

    Returns:
        配置值或默认值
    """
    try:
        return config_manager.get_config_value(key, default)
    except Exception:
        return default
