"""节点相关实体类"""
from typing import Any, Optional

from pydantic import BaseModel, Field


class NodeConfig(BaseModel):
    """节点配置"""
    id: str
    type: str
    config: dict[str, Any] = Field(default_factory=dict)
    display: Optional[dict[str, float]] = None  # {x, y}


class NodeDefinition(BaseModel):
    """节点类型定义（供编辑器面板使用）"""
    type: str
    label: str
    category: str
    category_icon: str = ""
    icon: str = ""
    description: str = ""
    config_schema: dict[str, Any] = Field(default_factory=dict)
    default_config: dict[str, Any] = Field(default_factory=dict)
    input_ports: list[str] = Field(default_factory=list)
    output_ports: list[str] = Field(default_factory=list)


class NodeTypeList(BaseModel):
    """节点类型列表（按类别分组）"""
    categories: list[dict[str, Any]]
