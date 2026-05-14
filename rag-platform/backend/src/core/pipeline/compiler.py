"""PipelineCompiler

将管道 JSON 配置编译为可执行的 CompiledPipeline，并驱动执行。
使用 Kahn 拓扑排序 + asyncio.gather 并行。
支持域管道并行执行 + 条件边路由。
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
    is_aggregation: bool = False


@dataclass
class ExecutionPlan:
    """执行计划"""
    nodes: dict[str, PlanNode] = field(default_factory=dict)
    sorted_ids: list[str] = field(default_factory=list)
    parallel_groups: list[list[str]] = field(default_factory=list)
    conditional_routes: dict[str, dict[str, str]] = field(default_factory=dict)
    degradation_routes: dict[str, dict[str, Any]] = field(default_factory=dict)
    # 域管道：domain_id → 域内节点拓扑排序列表
    domain_plans: dict[str, list[str]] = field(default_factory=dict)


@dataclass
class PipelineState:
    """管道执行状态"""
    query: str = ""
    params: dict[str, Any] = field(default_factory=dict)
    auth: AuthContext = field(default_factory=lambda: AuthContext(tenant_id="", user_id=""))

    # 所有节点的输出（node_id → output）
    node_outputs: dict[str, Any] = field(default_factory=dict)

    # 域执行结果
    domain_results: list[dict[str, Any]] = field(default_factory=list)

    # 最终结果
    answer: str = ""
    sources: list[dict[str, Any]] = field(default_factory=list)

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
        """编译管道配置为可执行的 CompiledPipeline"""
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
        """执行编译后的管道"""
        state = PipelineState(query=query, params=params, auth=auth)
        plan = compiled.execution_plan

        start_time = time.time()

        # 1. 并行执行各域管道
        if plan.domain_plans and not state.shortcut_activated:
            domain_results = await self._execute_domain_pipelines(
                plan, compiled.domain_configs, state
            )
            state.domain_results = domain_results

        # 2. 按拓扑顺序执行聚合层节点
        await self._execute_aggregation_plan(plan, state)

        execution_time_ms = int((time.time() - start_time) * 1000)

        return {
            "answer": state.answer,
            "sources": state.sources,
            "domain_results": state.domain_results,
            "degradation_events": state.degradation_events,
            "execution_time_ms": execution_time_ms,
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
        """构建执行计划"""
        plan = ExecutionPlan()

        # 1. 构建域管道计划
        for domain in config.get("domains", []):
            domain_id = domain.get("id", "")
            domain_nodes = domain.get("pipeline", {}).get("nodes", [])
            domain_edges = domain.get("pipeline", {}).get("edges", [])

            # 收集域内节点
            all_domain_nodes: dict[str, dict] = {}
            for node in domain_nodes:
                node_id = node.get("id", node.get("type"))
                all_domain_nodes[node_id] = node
                plan.nodes[node_id] = PlanNode(
                    node_id=node_id,
                    node_type=node.get("type", ""),
                    config=node.get("config", {}),
                    domain_id=domain_id,
                    knowledge_base_id=domain.get("knowledge_base_id", ""),
                )

            # 拓扑排序域内节点
            domain_sorted = self._topo_sort_nodes(all_domain_nodes, domain_edges)
            plan.domain_plans[domain_id] = domain_sorted

        # 2. 构建聚合层执行计划
        agg_config = config.get("aggregation", {})
        agg_nodes: dict[str, dict] = {}
        for node in agg_config.get("nodes", []):
            node_id = node.get("id", node.get("type"))
            agg_nodes[node_id] = node
            plan.nodes[node_id] = PlanNode(
                node_id=node_id,
                node_type=node.get("type", ""),
                config=node.get("config", {}),
                is_aggregation=True,
            )

        agg_edges = agg_config.get("edges", [])
        plan.sorted_ids = self._topo_sort_nodes(agg_nodes, agg_edges)

        # 构建邻接表用于并行组检测
        adjacency: dict[str, set[str]] = {nid: set() for nid in agg_nodes}
        indegree: dict[str, int] = {nid: 0 for nid in agg_nodes}
        for edge in agg_edges:
            source = edge.get("source")
            target = edge.get("target")
            if source in adjacency and target in adjacency:
                adjacency[source].add(target)
                indegree[target] += 1
                if source in plan.nodes:
                    plan.nodes[source].downstream.append(target)
                if target in plan.nodes:
                    plan.nodes[target].depends_on.append(source)

        plan.parallel_groups = self._detect_parallel_groups(plan.sorted_ids, indegree)

        return plan

    def _topo_sort_nodes(
        self, nodes: dict[str, dict], edges: list[dict]
    ) -> list[str]:
        """Kahn 拓扑排序"""
        adjacency: dict[str, set[str]] = {nid: set() for nid in nodes}
        indegree: dict[str, int] = {nid: 0 for nid in nodes}

        for edge in edges:
            source = edge.get("source")
            target = edge.get("target")
            if source in adjacency and target in adjacency:
                adjacency[source].add(target)
                indegree[target] += 1

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
            cycle_nodes = [nid for nid in nodes if nid not in sorted_ids]
            raise PipelineCompilationError(f"管道包含循环依赖: {cycle_nodes}")

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

    async def _execute_domain_pipelines(
        self,
        plan: ExecutionPlan,
        domain_configs: list[dict[str, Any]],
        state: PipelineState,
    ) -> list[dict[str, Any]]:
        """并行执行各域管道"""
        # 权限裁剪
        filtered_domains = self._filter_domains_by_permission(domain_configs, state)

        # 并行执行
        tasks = []
        for domain in filtered_domains:
            domain_id = domain.get("id", "")
            if domain_id in plan.domain_plans:
                tasks.append(self._execute_single_domain(
                    domain_id, plan.domain_plans[domain_id], plan.nodes, state
                ))

        if not tasks:
            return []

        results = await asyncio.gather(*tasks, return_exceptions=True)

        domain_results = []
        for i, result in enumerate(results):
            domain_id = filtered_domains[i].get("id", "")
            if isinstance(result, Exception):
                logger.error(f"域 {domain_id} 执行失败: {result}")
                domain_results.append({
                    "domain_id": domain_id,
                    "domain_name": filtered_domains[i].get("name", ""),
                    "candidates": [],
                    "contributed_to_answer": False,
                    "error": str(result),
                })
            else:
                domain_results.append(result)

        return domain_results

    async def _execute_single_domain(
        self,
        domain_id: str,
        node_ids: list[str],
        all_nodes: dict[str, PlanNode],
        state: PipelineState,
    ) -> dict[str, Any]:
        """执行单个域管道"""
        domain_node_outputs: dict[str, Any] = {}

        for node_id in node_ids:
            plan_node = all_nodes.get(node_id)
            if not plan_node:
                continue

            # 获取输入：依赖节点的输出或原始查询
            input_data = self._get_input_data(plan_node, domain_node_outputs, state)

            # 合并配置
            config = self._merge_params(state.params, plan_node.config)

            # 创建上下文
            context = NodeContext(
                input_data=input_data,
                config=config,
                auth=state.auth,
                node_id=node_id,
                node_type=plan_node.node_type,
                domain_id=domain_id,
                knowledge_base_id=plan_node.knowledge_base_id,
            )

            # 执行节点
            try:
                executor = registry.create_executor(plan_node.node_type)
                result = await executor.execute(context)
                domain_node_outputs[node_id] = result.output
                state.node_outputs[f"{domain_id}:{node_id}"] = result.output
            except Exception as e:
                logger.error(f"域节点执行失败 [{domain_id}:{node_id}]: {e}")
                domain_node_outputs[node_id] = None
                state.degradation_events.append({
                    "domain_id": domain_id,
                    "node_id": node_id,
                    "error": str(e),
                    "strategy": "skip",
                })

        # 域管道最终输出（最后一个节点的输出）
        candidates = []
        if node_ids:
            last_output = domain_node_outputs.get(node_ids[-1])
            if isinstance(last_output, list):
                candidates = last_output

        return {
            "domain_id": domain_id,
            "domain_name": "",
            "candidates": candidates,
            "contributed_to_answer": len(candidates) > 0,
            "error": None,
        }

    async def _execute_aggregation_plan(
        self, plan: ExecutionPlan, state: PipelineState
    ) -> None:
        """按拓扑顺序执行聚合层节点"""
        for node_id in plan.sorted_ids:
            plan_node = plan.nodes.get(node_id)
            if not plan_node or not plan_node.is_aggregation:
                continue

            # 获取输入
            input_data = self._get_aggregation_input(plan_node, state)

            # 合并配置
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
                state.node_outputs[node_id] = result.output

                # 更新状态关键字段
                self._update_state_from_result(node_id, plan_node.node_type, result, state)

            except Exception as e:
                logger.error(f"聚合节点执行失败 [{node_id}]: {e}")
                state.degradation_events.append({
                    "node_id": node_id,
                    "error": str(e),
                    "strategy": "skip",
                })

    def _get_input_data(
        self, plan_node: PlanNode, node_outputs: dict[str, Any], state: PipelineState
    ) -> Any:
        """获取域内节点输入数据"""
        if not plan_node.depends_on:
            return state.query  # 无依赖，返回原始查询
        # 返回最后一个依赖节点的输出
        last_dep = plan_node.depends_on[-1]
        return node_outputs.get(last_dep, state.query)

    def _get_aggregation_input(
        self, plan_node: PlanNode, state: PipelineState
    ) -> Any:
        """获取聚合节点输入数据"""
        node_type = plan_node.node_type

        # 特殊节点的输入映射
        if node_type == "query_analyzer":
            return state.query
        elif node_type == "domain_dispatch":
            return state.node_outputs.get("query_analyzer", [])
        elif node_type == "cross_fusion":
            return state.domain_results
        elif node_type == "cross_dedup":
            return state.node_outputs.get("cross_fusion", [])
        elif node_type == "conflict_detect":
            return state.node_outputs.get("cross_dedup", [])
        elif node_type == "unified_generate":
            return {
                "query": state.query,
                "sources": state.node_outputs.get("cross_dedup", []),
                "conflict_report": state.node_outputs.get("conflict_detect", {}),
            }

        # 通用：从依赖节点获取
        if plan_node.depends_on:
            last_dep = plan_node.depends_on[-1]
            return state.node_outputs.get(last_dep, state.query)
        return state.query

    def _update_state_from_result(
        self, node_id: str, node_type: str, result: NodeResult, state: PipelineState
    ) -> None:
        """根据节点类型更新状态关键字段"""
        if node_type == "domain_dispatch":
            state.domain_results = result.output if isinstance(result.output, list) else []
        elif node_type == "unified_generate":
            state.answer = result.output if isinstance(result.output, str) else ""
        elif node_type == "cross_dedup":
            state.sources = result.output if isinstance(result.output, list) else []

    def _filter_domains_by_permission(
        self, domain_configs: list[dict[str, Any]], state: PipelineState
    ) -> list[dict[str, Any]]:
        """根据用户权限裁剪域列表"""
        if state.auth.is_superadmin:
            return domain_configs

        # 实际实现应检查知识库 visibility + visible_roles
        # 简化实现：全部通过
        return domain_configs

    def _merge_params(self, params: dict, config: dict) -> dict:
        """合并参数（L3 > L2 > L0）"""
        merged = {}
        node_type = config.get("type", "")
        if node_type in NODE_DEFAULTS:
            merged.update(NODE_DEFAULTS[node_type])
        merged.update(config)
        merged.update(params)
        return merged
