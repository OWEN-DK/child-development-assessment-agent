"""域分发节点

并行启动各域管道 + 权限裁剪。
"""
from typing import Any

from src.core.pipeline.base_node import BaseNodeExecutor
from src.core.pipeline.node_context import NodeContext
from src.core.pipeline.node_result import NodeResult
from src.utils.logger import logger


class DomainDispatchExecutor(BaseNodeExecutor):
    """域分发执行器"""

    @property
    def category(self) -> str:
        return "aggregation"

    async def execute(self, context: NodeContext) -> NodeResult:
        """执行域分发"""
        domain_plans = context.input_data
        if not domain_plans:
            return NodeResult(output=[], node_id=context.node_id, node_type="domain_dispatch")

        parallel = context.config.get("parallel", True)
        timeout_ms = context.config.get("timeout_ms", 3000)
        max_concurrency = context.config.get("max_concurrency", 5)

        # 权限裁剪：过滤用户无权限的域
        filtered_plans = self._filter_by_permission(domain_plans, context)

        # 实际实现应 asyncio.gather 并行执行各域管道
        # 简化实现：返回空结果
        domain_results = []
        for plan in filtered_plans:
            domain_results.append({
                "domain_id": plan.get("domain_id", ""),
                "domain_name": plan.get("domain_name", ""),
                "candidates": [],
                "contributed_to_answer": True,
                "error": None,
            })

        return NodeResult(
            output=domain_results,
            metadata={
                "parallel": parallel,
                "timeout_ms": timeout_ms,
                "filtered_count": len(domain_plans) - len(filtered_plans),
            },
            node_id=context.node_id,
            node_type="domain_dispatch",
        )

    def _filter_by_permission(self, domain_plans: list, context: NodeContext) -> list:
        """根据用户权限裁剪域列表

        检查域配置中知识库的 visibility / visible_roles / owner_id。
        域配置应由调用方 enrich KB 元数据。
        """
        if context.auth.is_superadmin:
            return domain_plans

        filtered = []
        for plan in domain_plans:
            visibility = plan.get("visibility", "public")

            if visibility == "public":
                filtered.append(plan)
            elif visibility == "private":
                owner_id = plan.get("owner_id", "")
                if owner_id == context.auth.user_id:
                    filtered.append(plan)
            elif visibility == "role_scoped":
                visible_roles = plan.get("visible_roles", []) or []
                if any(slug in visible_roles for slug in context.auth.role_slugs):
                    filtered.append(plan)

        return filtered
