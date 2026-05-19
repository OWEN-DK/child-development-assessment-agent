"""配置字段元数据

供前端配置管理页面使用。
"""
from dataclasses import dataclass, field
from typing import Any, List


@dataclass
class ConfigFieldMetadata:
    """单个配置字段的元数据"""

    key: str
    category: str = ""
    description: str = ""
    hot_reloadable: bool = True
    requires_restart: bool = False
    affected_components: List[str] = field(default_factory=list)
    field_type: str = "str"
    default_value: Any = ""
    current_value: Any = ""
