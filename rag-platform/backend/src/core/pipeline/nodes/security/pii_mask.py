"""PII 脱敏节点"""
import re
from typing import Any

from src.core.pipeline.base_node import BaseNodeExecutor
from src.core.pipeline.node_context import NodeContext
from src.core.pipeline.node_result import NodeResult


class PIIMaskExecutor(BaseNodeExecutor):
    """PII 脱敏执行器"""

    # PII 正则模式
    PATTERNS = {
        "phone": r"1[3-9]\d{9}",
        "id_card": r"\d{17}[\dXx]",
        "email": r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
    }

    @property
    def category(self) -> str:
        return "security"

    async def execute(self, context: NodeContext) -> NodeResult:
        candidates = context.input_data
        target_types = context.config.get("target_types", ["phone", "id_card", "email"])
        mask_char = context.config.get("mask_char", "*")

        # 简化实现：不脱敏
        return NodeResult(
            output=candidates,
            metadata={"target_types": target_types},
            node_id=context.node_id,
            node_type="pii_mask",
        )
