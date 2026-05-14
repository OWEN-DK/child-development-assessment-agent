"""内容审核节点"""
from typing import Any

from src.core.pipeline.base_node import BaseNodeExecutor
from src.core.pipeline.node_context import NodeContext
from src.core.pipeline.node_result import NodeResult


class ContentAuditExecutor(BaseNodeExecutor):
    """内容审核执行器"""

    @property
    def category(self) -> str:
        return "security"

    async def execute(self, context: NodeContext) -> NodeResult:
        candidates = context.input_data
        audit_rules = context.config.get("audit_rules", [])
        threshold = context.config.get("threshold", 0.7)

        return NodeResult(
            output=candidates,
            metadata={"audit_rules": audit_rules, "threshold": threshold},
            node_id=context.node_id,
            node_type="content_audit",
        )
