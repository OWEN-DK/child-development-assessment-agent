"""配置元数据模块

定义配置字段的元数据结构。
"""

from dataclasses import dataclass
from typing import Any


@dataclass
class ConfigFieldMetadata:
    """配置字段元数据"""

    key: str
    category: str
    description: str
    hot_reloadable: bool
    requires_restart: bool
    affected_components: list[str]
    field_type: str
    default_value: Any
    current_value: Any = None
