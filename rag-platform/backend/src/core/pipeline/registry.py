"""节点注册表

单例模式，管理 28 种节点执行器的注册和查找。
"""
from typing import Optional

from src.core.pipeline.base_node import BaseNodeExecutor
from src.utils.logger import logger


class NodeRegistry:
    """节点注册表（单例）"""

    _instance: Optional["NodeRegistry"] = None
    _registry: dict[str, type[BaseNodeExecutor]] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._registry = {}
        return cls._instance

    def register(self, node_type: str, executor_class: type[BaseNodeExecutor]) -> None:
        """注册节点执行器

        Args:
            node_type: 节点类型标识（如 "query_rewrite"）
            executor_class: 执行器类
        """
        if node_type in self._registry:
            logger.warning(f"节点类型 {node_type} 已注册，将被覆盖")
        self._registry[node_type] = executor_class
        logger.debug(f"节点注册: {node_type} → {executor_class.__name__}")

    def get(self, node_type: str) -> type[BaseNodeExecutor]:
        """获取节点执行器类

        Args:
            node_type: 节点类型标识

        Returns:
            执行器类

        Raises:
            KeyError: 节点类型未注册
        """
        if node_type not in self._registry:
            raise KeyError(f"节点类型未注册: {node_type}")
        return self._registry[node_type]

    def create_executor(self, node_type: str) -> BaseNodeExecutor:
        """创建节点执行器实例

        Args:
            node_type: 节点类型标识

        Returns:
            执行器实例
        """
        executor_class = self.get(node_type)
        return executor_class()

    def list_types(self) -> list[str]:
        """列出所有已注册的节点类型"""
        return list(self._registry.keys())

    def list_by_category(self) -> dict[str, list[str]]:
        """按类别列出节点类型"""
        categories: dict[str, list[str]] = {}
        for node_type, executor_class in self._registry.items():
            # 实例化以获取 category 属性
            try:
                instance = executor_class()
                cat = instance.category
            except Exception:
                cat = "unknown"
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(node_type)
        return categories

    def clear(self) -> None:
        """清空注册表（测试用）"""
        self._registry.clear()


# 全局单例
registry = NodeRegistry()
