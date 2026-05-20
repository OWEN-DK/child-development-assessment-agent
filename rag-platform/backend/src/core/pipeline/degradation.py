"""降级链

节点执行失败时按优先级尝试降级策略：
skip_node → reroute → degrade_cache → abort
"""
from typing import Any, Optional

from src.core.pipeline.base_node import BaseNodeExecutor
from src.core.pipeline.exceptions import (
    DegradationChainExhaustedError,
    NodeExecutionError,
)
from src.core.pipeline.node_context import NodeContext
from src.core.pipeline.node_result import NodeResult
from src.core.pipeline.registry import registry
from src.utils.exceptions import InvalidParamsException
from src.utils.logger import logger


class DegradationRegistry:
    """降级策略注册表

    按 node_id 存储降级策略链。策略按优先级排列：
    skip_node → reroute → degrade_cache → abort
    """

    def __init__(self):
        self._routes: dict[str, dict[str, Any]] = {}

    def register(
        self,
        node_id: str,
        strategies: list[str],
        alternate_node_id: str = "",
        cache_key: str = "",
    ) -> None:
        """注册节点降级策略

        Args:
            node_id: 节点 ID
            strategies: 策略列表（已按优先级排列）
            alternate_node_id: reroute 策略的备选节点 ID
            cache_key: degrade_cache 策略的缓存键
        """
        self._routes[node_id] = {
            "strategies": strategies,
            "alternate_node_id": alternate_node_id,
            "cache_key": cache_key,
        }

    def get_chain(self, node_id: str) -> list[str]:
        """获取节点降级策略链"""
        route = self._routes.get(node_id, {})
        strategies = list(route.get("strategies", []))
        if "abort" not in strategies:
            strategies.append("abort")
        return strategies

    def get_alternate_node(self, node_id: str) -> str:
        """获取 reroute 备选节点 ID"""
        return self._routes.get(node_id, {}).get("alternate_node_id", "")

    def get_cache_key(self, node_id: str) -> str:
        """获取 degrade_cache 缓存键"""
        return self._routes.get(node_id, {}).get("cache_key", "")

    def build_from_pipeline_config(self, config: dict[str, Any]) -> None:
        """从管道配置构建降级路由

        Args:
            config: 管道 JSON 配置
        """
        for domain in config.get("domains", []):
            for edge in domain.get("pipeline", {}).get("degradation_edges", []):
                self._register_edge(edge)

        for edge in config.get("aggregation", {}).get("degradation_edges", []):
            self._register_edge(edge)

    def _register_edge(self, edge: dict[str, Any]) -> None:
        """注册单条降级边"""
        source = edge.get("source", "")
        if not source:
            return
        self.register(
            node_id=source,
            strategies=edge.get("strategies", ["skip_node"]),
            alternate_node_id=edge.get("alternate_node_id", ""),
            cache_key=edge.get("cache_key", ""),
        )

    def clear(self) -> None:
        """清空注册表（测试用）"""
        self._routes.clear()


class NodeExecutorWrapper:
    """节点执行器包装器

    在节点执行外层处理降级：捕获异常 → 查注册表 → 按优先级尝试策略。
    降级链式传递但不递归——A 降级到 B 后，B 失败不再触发 B 的降级。
    """

    def __init__(self, degradation_registry: DegradationRegistry):
        self._degradation = degradation_registry

    async def execute(
        self,
        node_id: str,
        context: NodeContext,
        alternate_context: Optional[NodeContext] = None,
        _depth: int = 0,
    ) -> NodeResult:
        """包装执行节点，自动处理降级

        Args:
            node_id: 节点 ID
            context: 节点执行上下文
            alternate_context: reroute 备选上下文（由调用方传入）
            _depth: 降级递归深度（内部追踪，上限 2）

        Returns:
            NodeResult 执行结果（可能被降级修饰）

        Raises:
            DegradationChainExhaustedError: 所有降级策略均失败
        """
        executor = registry.create_executor(context.node_type)

        try:
            result = await executor.execute(context)
            result.node_id = node_id
            result.node_type = context.node_type
            return result
        except Exception as exc:
            strategies = self._degradation.get_chain(node_id)

            for strategy in strategies:
                try:
                    result = await self._apply_strategy(
                        strategy, node_id, context, alternate_context, exc, _depth
                    )
                    if result is not None:
                        return result
                except Exception:
                    continue

            raise DegradationChainExhaustedError(
                node_id=node_id, strategies_tried=strategies
            )

    async def _apply_strategy(
        self,
        strategy: str,
        node_id: str,
        context: NodeContext,
        alternate_context: Optional[NodeContext],
        error: Exception,
        depth: int,
    ) -> Optional[NodeResult]:
        """执行单个降级策略"""
        if strategy == "skip_node":
            return NodeResult(
                output=context.input_data,
                degraded=True,
                degradation_strategy="skip_node",
                degradation_reason=str(error),
                node_id=node_id,
                node_type=context.node_type,
            )

        elif strategy == "reroute":
            alt_node_id = self._degradation.get_alternate_node(node_id)
            if not alt_node_id or depth >= 1:
                raise InvalidParamsException(message="reroute 需要备选节点且不允许递归降级")

            alt_ctx = alternate_context or context
            alt_ctx.node_id = alt_node_id

            try:
                alt_executor = registry.create_executor(alt_ctx.node_type)
                result = await alt_executor.execute(alt_ctx)
                result.node_id = alt_node_id
                result.degraded = True
                result.degradation_strategy = "reroute"
                result.degradation_reason = (
                    f"从 {node_id} 降级路由: {str(error)}"
                )
                return result
            except Exception as alt_error:
                logger.warning(f"reroute 备选节点 [{alt_node_id}] 也失败了: {alt_error}")
                raise

        elif strategy == "degrade_cache":
            cache_key = self._degradation.get_cache_key(node_id)
            if not cache_key:
                raise InvalidParamsException(message="degrade_cache 需要缓存键")

            cached = await self._get_cached_result(cache_key)
            if cached is None:
                raise InvalidParamsException(message="无可用缓存")
            return NodeResult(
                output=cached,
                degraded=True,
                degradation_strategy="degrade_cache",
                degradation_reason=f"节点 {node_id} 失败，使用缓存: {str(error)}",
                node_id=node_id,
                node_type=context.node_type,
            )

        elif strategy == "abort":
            raise NodeExecutionError(
                node_id=node_id,
                node_type=context.node_type,
                message=str(error),
                cause=error,
            )

        return None

    async def _get_cached_result(self, cache_key: str) -> Any:
        """获取降级缓存结果"""
        try:
            from src.service.cache.redis_cache import RedisCache

            c = RedisCache()
            return await c.get(cache_key)
        except Exception:
            return None
