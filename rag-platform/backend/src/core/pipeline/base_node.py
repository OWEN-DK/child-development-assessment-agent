"""节点执行器抽象基类"""
from abc import ABC, abstractmethod
from typing import Any

from src.core.pipeline.node_context import NodeContext
from src.core.pipeline.node_result import NodeResult


class BaseNodeExecutor(ABC):
    """节点执行器抽象基类

    所有 28 种节点执行器必须继承此类并实现 execute 方法。
    """

    @abstractmethod
    async def execute(self, context: NodeContext) -> NodeResult:
        """执行节点

        Args:
            context: 节点执行上下文

        Returns:
            NodeResult 执行结果
        """

    def validate_config(self, config: dict[str, Any]) -> list[str]:
        """校验节点配置

        Args:
            config: 节点配置

        Returns:
            错误消息列表（空表示校验通过）
        """
        return []

    @property
    def node_type(self) -> str:
        """节点类型标识"""
        return self.__class__.__name__

    @property
    def category(self) -> str:
        """节点类别（query/retrieval/security/quality/performance/synthesis/aggregation）"""
        return "unknown"

    @property
    def input_type(self) -> str:
        """输入数据类型"""
        return "any"

    @property
    def output_type(self) -> str:
        """输出数据类型"""
        return "any"
