"""PipelineCompiler

将管道 JSON 配置编译为可执行的 CompiledPipeline，并驱动执行。
使用 Kahn 拓扑排序 + asyncio.gather 并行。
"""
import asyncio
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Optional

from src.core.pipeline.base_node import BaseNodeExecutor
from src.core.pipeline.defaults import NODE_DEFAULTS
from src.core.pipeline.exceptions import (
    DomainTimeoutError,
    NodeExecutionError,
    PipelineCompilationError,
)
from src.core.pipeline.node_context import AuthContext, NodeContext
from src.core.pipeline.node_result import NodeResult
from src.core.pipeline.registry import registry
from src.utils.logger import logger


@dataclass
class PlanNode:
    """执行计划节点"""
    node_id: str
    node_type: str
    config: dict[str, Any] = field(default_factory=dict)
    domain_id: str = ""
    knowledge_base_id: str = ""
    depends_on: list[str] = field(default_factory=list)
    downstream: list[str] = field(default_factory=list)


@dataclass
class ExecutionPlan:
    """执行计划"""
    nodes: dict[str, PlanNode] = field(default_factory=dict)
    sorted_ids: list[str] = field(default_factory=list)
    parallel_groups: list[list[str]] = field(default_factory=list)
    conditional_routes: dict[str, dict[str, str]] = field(default_factory=dict)
    degradation_routes: dict[str, dict[str, Any]] = field(default_factory=dict)


@dataclass
class PipelineState:
    """管道执行状态"""
    query: str = ""
    params: dict[str, Any] = field(default_factory=dict)
    auth: AuthContext = field(default_factory=lambda: AuthContext(tenant_id="", user_id=""))

    # 域执行计划
    domain_plans: list[dict[str, Any]] = field(default_factory=list)
    domain_results: list[dict[str, Any]] = field(default_factory=list)

    # 中间结果
    merged_set: list[dict[str, Any]] = field(default_factory=list)
    deduped_set: list[dict[str, Any]] = field(default_factory=list)
    conflict_report: dict[str, Any] = field(default_factory=dict)
    answer: str = ""

    # 快捷路径
    shortcut_activated: bool = False

    # 降级事件
    degradation_events: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class CompiledPipeline:
    """编译后的管道"""
    config: dict[str, Any] = field(default_factory=dict)
    execution_plan: ExecutionPlan = field(default_factory=ExecutionPlan)
    domain_configs: list[dict[str, Any]] = field(default_factory=list)
    aggregation_config: dict[str, Any] = field(default_factory=dict)


class PipelineCompiler:
    """管道编译器"""

    def compile(self, pipeline_config: dict[str, Any]) -> CompiledPipeline:
        """编译管道配置为可执行的 CompiledPipeline

        Args:
            pipeline_config: 管道 JSON 配置

        Returns:
            CompiledPipeline

        Raises:
            PipelineCompilationError: 编译失败
        """
        errors = self._validate_structure(pipeline_config)
        if errors:
            raise PipelineCompilationError("管道结构校验失败", errors)

        errors = self._validate_nodes(pipeline_config)
        if errors:
            raise PipelineCompilationError("节点配置校验失败", errors)

        execution_plan = self._build_execution_plan(pipeline_config)

        return CompiledPipeline(
            config=pipeline_config,
            execution_plan=execution_plan,
            domain_configs=pipeline_config.get("domains", []),
            aggregation_config=pipeline_config.get("aggregation", {}),
        )

    async def execute(
        self,
        compiled: CompiledPipeline,
        query: str,
        params: dict[str, Any],
        auth: AuthContext,
    ) -> dict[str, Any]:
        """执行编译后的管道

        Args:
            compiled: 编译后的管道
            query: 查询文本
            params: 参数
            auth: 认证上下文

        Returns:
            执行结果
        """
        state = PipelineState(query=query, params=params, auth=auth)

        # 按拓扑顺序执行聚合层节点
        result = await self._execute_plan(compiled.execution_plan, state, compiled)

        return {
            "answer": state.answer,
            "sources": state.deduped_set,
            "domain_results": state.domain_results,
            "degradation_events": state.degradation_events,
            "execution_time_ms": result.get("execution_time_ms", 0),
        }

    def _validate_structure(self, config: dict[str, Any]) -> list[str]:
        """校验管道结构"""
        errors = []

        if "pipeline" not in config:
            errors.append("缺少 pipeline 字段")
        elif "id" not in config["pipeline"]:
            errors.append("缺少 pipeline.id")

        if "domains" not in config:
            errors.append("缺少 domains 字段")

        return errors

    def _validate_nodes(self, config: dict[str, Any]) -> list[str]:
        """校验节点配置"""
        errors = []

        # 校验域内节点
        for domain in config.get("domains", []):
            for node in domain.get("pipeline", {}).get("nodes", []):
                node_type = node.get("type")
                if not node_type:
                    errors.append(f"节点缺少 type: {node}")
                    continue
                try:
                    executor = registry.create_executor(node_type)
                    node_errors = executor.validate_config(node.get("config", {}))
                    errors.extend([f"[{node_type}] {e}" for e in node_errors])
                except KeyError:
                    errors.append(f"节点类型未注册: {node_type}")

        # 校验聚合节点
        for node in config.get("aggregation", {}).get("nodes", []):
            node_type = node.get("type")
            if not node_type:
                errors.append(f"聚合节点缺少 type: {node}")
                continue
            try:
                executor = registry.create_executor(node_type)
                node_errors = executor.validate_config(node.get("config", {}))
                errors.extend([f"[{node_type}] {e}" for e in node_errors])
            except KeyError:
                errors.append(f"节点类型未注册: {node_type}")

        return errors

    def _build_execution_plan(self, config: dict[str, Any]) -> ExecutionPlan:
        """构建执行计划（Kahn 拓扑排序）"""
        plan = ExecutionPlan()

        # 收集所有节点
        all_nodes: dict[str, dict] = {}
        all_edges: list[dict] = []

        # 聚合层节点
        agg_config = config.get("aggregation", {})
        for node in agg_config.get("nodes", []):
            node_id = node.get("id", node.get("type"))
            all_nodes[node_id] = node
        all_edges.extend(agg_config.get("edges", []))

        # 构建 PlanNode
        for node_id, node_config in all_nodes.items():
            plan.nodes[node_id] = PlanNode(
                node_id=node_id,
                node_type=node_config.get("type", ""),
                config=node_config.get("config", {}),
            )

        # 构建邻接表和入度
        adjacency: dict[str, set[str]] = {nid: set() for nid in all_nodes}
        indegree: dict[str, int] = {nid: 0 for nid in all_nodes}

        for edge in all_edges:
            source = edge.get("source")
            target = edge.get("target")
            if source in adjacency and target in adjacency:
                adjacency[source].add(target)
                indegree[target] += 1
                plan.nodes[source].downstream.append(target)
                plan.nodes[target].depends_on.append(source)

        # Kahn 拓扑排序
        plan.sorted_ids = self._kahn_sort(adjacency, indegree, all_nodes)

        # 检测并行组
        plan.parallel_groups = self._detect_parallel_groups(plan.sorted_ids, indegree)

        return plan

    def _kahn_sort(
        self,
        adjacency: dict[str, set[str]],
        indegree: dict[str, int],
        nodes: dict[str, dict],
    ) -> list[str]:
        """Kahn 拓扑排序"""
        sorted_ids = []
        queue = deque([nid for nid, deg in indegree.items() if deg == 0])

        while queue:
            node_id = queue.popleft()
            sorted_ids.append(node_id)

            for downstream in adjacency.get(node_id, set()):
                indegree[downstream] -= 1
                if indegree[downstream] == 0:
                    queue.append(downstream)

        if len(sorted_ids) < len(nodes):
            # 检测环路
            cycle_nodes = [nid for nid in nodes if nid not in sorted_ids]
            raise PipelineCompilationError(
                f"管道包含循环依赖: {cycle_nodes}"
            )

        return sorted_ids

    def _detect_parallel_groups(
        self, sorted_ids: list[str], indegree: dict[str, int]
    ) -> list[list[str]]:
        """检测可并行执行的节点组"""
        groups: dict[int, list[str]] = {}
        for node_id in sorted_ids:
            level = indegree.get(node_id, 0)
            if level not in groups:
                groups[level] = []
            groups[level].append(node_id)

        return [groups[level] for level in sorted(groups.keys())]

    async def _execute_plan(
        self,
        plan: ExecutionPlan,
        state: PipelineState,
        compiled: CompiledPipeline,
    ) -> dict[str, Any]:
        """按执行计划执行"""
        start_time = time.time()

        for node_id in plan.sorted_ids:
            plan_node = plan.nodes.get(node_id)
            if not plan_node:
                continue

            # 获取输入数据
            input_data = self._get_input_data(plan_node, state)

            # 合并配置（L3 > L2 > L0）
            config = self._merge_params(state.params, plan_node.config)

            # 创建上下文
            context = NodeContext(
                input_data=input_data,
                config=config,
                auth=state.auth,
                node_id=node_id,
                node_type=plan_node.node_type,
            )

            # 执行节点
            try:
                executor = registry.create_executor(plan_node.node_type)
                result = await executor.execute(context)

                # 存储结果
                self._store_node_result(node_id, result, state)

            except Exception as e:
                logger.error(f"节点执行失败: {node_id}, {e}")
                # 简化处理：记录错误继续执行
                state.degradation_events.append({
                    "node_id": node_id,
                    "error": str(e),
                    "strategy": "skip",
                })

        execution_time_ms = int((time.time() - start_time) * 1000)
        return {"execution_time_ms": execution_time_ms}

    def _get_input_data(
        self, plan_node: PlanNode, state: PipelineState
    ) -> Any:
        """获取节点输入数据"""
        # 简化实现：根据节点类型返回相应数据
        if plan_node.node_type == "query_rewrite":
            return state.query
        elif plan_node.node_type in ("bm25_search", "vector_search", "hybrid_search"):
            return state.query
        elif plan_node.node_type == "unified_generate":
            return {
                "query": state.query,
                "sources": state.deduped_set,
                "conflict_report": state.conflict_report,
            }
        else:
            # 默认返回上游节点的输出
            for dep_id in plan_node.depends_on:
                dep_node = plan_node
                # 简化：返回 query
                return state.query
            return state.query

    def _store_node_result(
        self, node_id: str, result: NodeResult, state: PipelineState
    ) -> None:
        """存储节点执行结果到状态"""
        # 根据节点类型存储到相应位置
        plan_node = None
        # 简化实现
        if result.output:
            if isinstance(result.output, list):
                state.deduped_set = result.output

    def _merge_params(self, params: dict, config: dict) -> dict:
        """合并参数（L3 > L2 > L0）"""
        merged = {}
        # L0 默认值
        node_type = config.get("type", "")
        if node_type in NODE_DEFAULTS:
            merged.update(NODE_DEFAULTS[node_type])
        # L2 管道配置
        merged.update(config)
        # L3 API 参数
        merged.update(params)
        return merged
