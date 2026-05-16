"""PipelineCompiler

将管道 JSON 配置编译为可执行的 CompiledPipeline，并驱动执行。
使用 Kahn 拓扑排序 + asyncio.gather 并行。
支持域管道并行执行 + 条件边路由 + 降级链。
"""
import asyncio
import time
from collections import deque
from typing import Any

from src.core.pipeline.compiled_pipeline import (
    CompiledPipeline,
    ExecutionPlan,
    PipelineState,
    PlanNode,
)
from src.core.pipeline.defaults import NODE_DEFAULTS
from src.core.pipeline.exceptions import (
    DomainTimeoutError,
    PipelineCompilationError,
)
from src.core.pipeline.degradation import DegradationRegistry, NodeExecutorWrapper
from src.core.pipeline.node_context import AuthContext, NodeContext
from src.core.pipeline.node_result import NodeResult
from src.core.pipeline.registry import registry
from src.utils.logger import logger


class PipelineCompiler:
    """管道编译器

    编译管道 JSON → CompiledPipeline → 驱动执行。
    """

    def __init__(self):
        self._degradation = DegradationRegistry()
        self._wrapper = NodeExecutorWrapper(self._degradation)

    def compile(self, pipeline_config: dict[str, Any]) -> CompiledPipeline:
        """编译管道配置为可执行的 CompiledPipeline"""
        errors = self._validate_structure(pipeline_config)
        if errors:
            raise PipelineCompilationError("管道结构校验失败", errors)

        errors = self._validate_nodes(pipeline_config)
        if errors:
            raise PipelineCompilationError("节点配置校验失败", errors)

        # 从配置构建降级路由
        self._degradation.clear()
        self._degradation.build_from_pipeline_config(pipeline_config)

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

        # 重新从配置构建降级路由（execute 可能用不同的 compiler 实例）
        if not self._degradation._routes:
            self._degradation.build_from_pipeline_config(compiled.config)

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

    # ── 校验 ──────────────────────────────────────────

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

    # ── 编译 ──────────────────────────────────────────

    def _build_execution_plan(self, config: dict[str, Any]) -> ExecutionPlan:
        """构建执行计划"""
        plan = ExecutionPlan()

        # 1. 构建域管道计划
        for domain in config.get("domains", []):
            domain_id = domain.get("id", "")
            domain_nodes = domain.get("pipeline", {}).get("nodes", [])
            domain_edges = domain.get("pipeline", {}).get("edges", [])
            deg_edges = domain.get("pipeline", {}).get("degradation_edges", [])

            all_domain_nodes: dict[str, dict] = {}
            for node in domain_nodes:
                node_id = node.get("id", node.get("type"))
                all_domain_nodes[node_id] = node

                # 提取降级信息
                deg_strategies, alt_node = self._extract_degradation(node_id, deg_edges)
                plan.nodes[node_id] = PlanNode(
                    node_id=node_id,
                    node_type=node.get("type", ""),
                    config=node.get("config", {}),
                    domain_id=domain_id,
                    knowledge_base_id=domain.get("knowledge_base_id", ""),
                    degradation_strategies=deg_strategies,
                    alternate_node_id=alt_node,
                )

            domain_sorted = self._topo_sort_nodes(all_domain_nodes, domain_edges)
            plan.domain_plans[domain_id] = domain_sorted

        # 2. 构建聚合层执行计划
        agg_config = config.get("aggregation", {})
        agg_nodes: dict[str, dict] = {}
        agg_deg_edges = agg_config.get("degradation_edges", [])
        for node in agg_config.get("nodes", []):
            node_id = node.get("id", node.get("type"))
            agg_nodes[node_id] = node

            deg_strategies, alt_node = self._extract_degradation(node_id, agg_deg_edges)
            plan.nodes[node_id] = PlanNode(
                node_id=node_id,
                node_type=node.get("type", ""),
                config=node.get("config", {}),
                is_aggregation=True,
                degradation_strategies=deg_strategies,
                alternate_node_id=alt_node,
            )

        agg_edges = agg_config.get("edges", [])
        plan.sorted_ids = self._topo_sort_nodes(agg_nodes, agg_edges)

        # 构建邻接表
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

    def _extract_degradation(
        self, node_id: str, deg_edges: list[dict]
    ) -> tuple[list[str], str]:
        """从降级边中提取节点降级策略"""
        for edge in deg_edges:
            if edge.get("source") == node_id:
                return (
                    edge.get("strategies", ["skip_node"]),
                    edge.get("alternate_node_id", ""),
                )
        return ([], "")

    # ── 拓扑排序 ──────────────────────────────────────

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

    # ── 执行 ──────────────────────────────────────────

    async def _execute_domain_pipelines(
        self,
        plan: ExecutionPlan,
        domain_configs: list[dict[str, Any]],
        state: PipelineState,
    ) -> list[dict[str, Any]]:
        """并行执行各域管道"""
        filtered_domains = self._filter_domains_by_permission(domain_configs, state)

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
        """执行单个域管道（含降级支持）"""
        domain_node_outputs: dict[str, Any] = {}

        for node_id in node_ids:
            plan_node = all_nodes.get(node_id)
            if not plan_node:
                continue

            input_data = self._get_input_data(plan_node, domain_node_outputs, state)
            config = self._merge_params(state.params, plan_node.config)

            context = NodeContext(
                input_data=input_data,
                config=config,
                auth=state.auth,
                node_id=node_id,
                node_type=plan_node.node_type,
                domain_id=domain_id,
                knowledge_base_id=plan_node.knowledge_base_id,
            )

            result = await self._execute_node_with_degradation(
                plan_node, context, state
            )
            domain_node_outputs[node_id] = result.output
            state.node_outputs[f"{domain_id}:{node_id}"] = result.output

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
        """按拓扑顺序执行聚合层节点（含降级支持）"""
        for node_id in plan.sorted_ids:
            plan_node = plan.nodes.get(node_id)
            if not plan_node or not plan_node.is_aggregation:
                continue

            input_data = self._get_aggregation_input(plan_node, state)
            config = self._merge_params(state.params, plan_node.config)

            context = NodeContext(
                input_data=input_data,
                config=config,
                auth=state.auth,
                node_id=node_id,
                node_type=plan_node.node_type,
            )

            result = await self._execute_node_with_degradation(
                plan_node, context, state
            )
            state.node_outputs[node_id] = result.output
            self._update_state_from_result(node_id, plan_node.node_type, result, state)

    async def _execute_node_with_degradation(
        self,
        plan_node: PlanNode,
        context: NodeContext,
        state: PipelineState,
    ) -> NodeResult:
        """使用降级包装器执行节点

        节点失败时通过 DegradationRegistry 查降级策略，
        按 skip_node → reroute → degrade_cache → abort 顺序尝试。
        """
        try:
            return await self._wrapper.execute(plan_node.node_id, context)
        except Exception as exc:
            logger.error(
                f"节点执行失败 [{plan_node.node_id}]: {exc}"
            )
            state.degradation_events.append({
                "domain_id": plan_node.domain_id,
                "node_id": plan_node.node_id,
                "node_type": plan_node.node_type,
                "error": str(exc),
                "strategy": "abort",
            })
            # 记录失败并返回空结果以不阻塞管道
            return NodeResult(
                output=None,
                degraded=True,
                degradation_strategy="abort",
                degradation_reason=str(exc),
                node_id=plan_node.node_id,
                node_type=plan_node.node_type,
            )

    # ── 输入数据映射 ──────────────────────────────────

    def _get_input_data(
        self, plan_node: PlanNode, node_outputs: dict[str, Any], state: PipelineState
    ) -> Any:
        """获取域内节点输入数据"""
        if not plan_node.depends_on:
            return state.query
        last_dep = plan_node.depends_on[-1]
        return node_outputs.get(last_dep, state.query)

    def _get_aggregation_input(
        self, plan_node: PlanNode, state: PipelineState
    ) -> Any:
        """获取聚合节点输入数据"""
        node_type = plan_node.node_type

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

        if plan_node.depends_on:
            last_dep = plan_node.depends_on[-1]
            return state.node_outputs.get(last_dep, state.query)
        return state.query

    # ── 状态更新 ──────────────────────────────────────

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

    # ── 权限 ──────────────────────────────────────────

    def _filter_domains_by_permission(
        self, domain_configs: list[dict[str, Any]], state: PipelineState
    ) -> list[dict[str, Any]]:
        """根据用户权限裁剪域列表"""
        if state.auth.is_superadmin:
            return domain_configs

        filtered = []
        for domain in domain_configs:
            visibility = domain.get("visibility", "public")

            if visibility == "public":
                filtered.append(domain)
            elif visibility == "private":
                owner_id = domain.get("owner_id", "")
                if owner_id == state.auth.user_id:
                    filtered.append(domain)
            elif visibility == "role_scoped":
                visible_roles = domain.get("visible_roles", []) or []
                if any(slug in visible_roles for slug in state.auth.role_slugs):
                    filtered.append(domain)

        if len(filtered) < len(domain_configs):
            logger.info(
                f"域权限裁剪: {len(domain_configs)} → {len(filtered)} "
                f"(用户 {state.auth.user_id} 角色 {state.auth.role_slugs})"
            )

        return filtered

    # ── 配置覆盖 ──────────────────────────────────────

    def _merge_params(self, params: dict, config: dict) -> dict:
        """合并参数（L3 > L2 > L0）"""
        merged = {}
        node_type = config.get("type", "")
        if node_type in NODE_DEFAULTS:
            merged.update(NODE_DEFAULTS[node_type])
        merged.update(config)
        merged.update(params)
        return merged
