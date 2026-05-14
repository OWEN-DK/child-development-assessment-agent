"""结果融合节点

多分支 CandidateSet → RRF/加权融合。
"""
from typing import Any

from src.core.pipeline.base_node import BaseNodeExecutor
from src.core.pipeline.node_context import NodeContext
from src.core.pipeline.node_result import NodeResult


class ResultFusionExecutor(BaseNodeExecutor):
    """结果融合执行器"""

    @property
    def category(self) -> str:
        return "retrieval"

    async def execute(self, context: NodeContext) -> NodeResult:
        """执行结果融合"""
        candidate_sets = context.input_data
        if not candidate_sets:
            return NodeResult(output=[], node_id=context.node_id, node_type="result_fusion")

        fusion_method = context.config.get("fusion_method", "rrf")
        final_top_k = context.config.get("final_top_k", 10)

        # 简化实现：合并所有候选集
        merged = []
        if isinstance(candidate_sets, list):
            for candidates in candidate_sets:
                if isinstance(candidates, list):
                    merged.extend(candidates)

        return NodeResult(
            output=merged[:final_top_k],
            metadata={"fusion_method": fusion_method, "final_top_k": final_top_k},
            node_id=context.node_id,
            node_type="result_fusion",
        )
