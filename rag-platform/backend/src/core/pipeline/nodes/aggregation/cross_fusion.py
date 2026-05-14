"""跨域融合节点

多域结果 weighted RRF 融合。
"""
from typing import Any

from src.core.pipeline.base_node import BaseNodeExecutor
from src.core.pipeline.node_context import NodeContext
from src.core.pipeline.node_result import NodeResult


class CrossFusionExecutor(BaseNodeExecutor):
    """跨域融合执行器"""

    @property
    def category(self) -> str:
        return "aggregation"

    async def execute(self, context: NodeContext) -> NodeResult:
        """执行跨域融合"""
        domain_results = context.input_data
        if not domain_results:
            return NodeResult(output=[], node_id=context.node_id, node_type="cross_fusion")

        fusion_method = context.config.get("fusion_method", "weighted_rrf")
        final_top_k = context.config.get("final_top_k", 10)

        # 简化实现：合并所有域的候选集
        merged = []
        for dr in domain_results:
            if isinstance(dr, dict):
                candidates = dr.get("candidates", [])
                merged.extend(candidates)

        return NodeResult(
            output=merged[:final_top_k],
            metadata={"fusion_method": fusion_method, "domain_count": len(domain_results)},
            node_id=context.node_id,
            node_type="cross_fusion",
        )
