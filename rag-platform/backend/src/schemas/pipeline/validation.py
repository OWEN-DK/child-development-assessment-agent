"""管道校验相关实体类"""
from typing import Any, Optional

from pydantic import BaseModel, Field


class ValidationError(BaseModel):
    """单条校验错误"""
    location: str = Field(description="错误位置（如 node_id 或 edge_id）")
    error_type: str = Field(description="错误类型（structure/node/edge/compilation）")
    message: str = Field(description="错误描述")


class ValidationResult(BaseModel):
    """管道校验结果"""
    valid: bool = Field(description="是否通过校验")
    errors: list[ValidationError] = Field(default_factory=list, description="错误列表")
    node_count: int = Field(default=0, description="节点总数")
    edge_count: int = Field(default=0, description="边总数")
    domain_count: int = Field(default=0, description="域数量")


class DryRunResult(BaseModel):
    """干运行结果"""
    compilable: bool = Field(description="是否可编译")
    errors: list[ValidationError] = Field(default_factory=list, description="编译错误列表")
    execution_plan_summary: Optional[dict[str, Any]] = Field(
        default=None, description="执行计划摘要（拓扑排序、并行组）"
    )
    registered_node_types: list[str] = Field(
        default_factory=list, description="涉及的节点类型"
    )
    unregistered_node_types: list[str] = Field(
        default_factory=list, description="未注册的节点类型"
    )


class NodeTypeInfo(BaseModel):
    """节点类型信息"""
    type: str = Field(description="节点类型标识")
    category: str = Field(description="所属类别")
    label: str = Field(default="", description="显示名称")
    description: str = Field(default="", description="节点描述")
    default_config: dict[str, Any] = Field(default_factory=dict, description="默认配置")
    input_ports: list[str] = Field(default_factory=list, description="输入端口")
    output_ports: list[str] = Field(default_factory=list, description="输出端口")


class NodeTypeCategory(BaseModel):
    """节点类型分类"""
    name: str = Field(description="类别名称")
    icon: str = Field(default="", description="类别图标")
    types: list[NodeTypeInfo] = Field(default_factory=list, description="该类别下的节点类型")


class NodeTypeListResponse(BaseModel):
    """节点类型列表响应"""
    categories: list[NodeTypeCategory] = Field(default_factory=list, description="按类别分组的节点类型")
    total: int = Field(default=0, description="节点类型总数")
