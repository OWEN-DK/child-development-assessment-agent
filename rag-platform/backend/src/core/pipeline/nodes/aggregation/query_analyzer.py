"""查询分析节点

LLM 调用识别查询涉及的域，输出域执行计划。
"""
from typing import Any

from src.core.pipeline.base_node import BaseNodeExecutor
from src.core.pipeline.node_context import NodeContext
from src.core.pipeline.node_result import NodeResult
from src.utils.logger import logger


class QueryAnalyzerExecutor(BaseNodeExecutor):
    """查询分析执行器"""

    @property
    def category(self) -> str:
        return "aggregation"

    async def execute(self, context: NodeContext) -> NodeResult:
        """执行查询分析"""
        query = context.input_data
        if not query:
            return NodeResult(output=[], node_id=context.node_id, node_type="query_analyzer")

        max_domains = context.config.get("max_domains", 5)
        min_confidence = context.config.get("min_confidence", 0.6)

        # 实际实现应调用 LLM 识别涉及的域
        # 简化实现：返回默认域
        domain_plans = [
            {
                "domain_id": "default",
                "domain_name": "默认域",
                "knowledge_base_id": "",
                "confidence": 1.0,
                "reason": "默认路由",
            }
        ]

        # 单域快捷路径
        if len(domain_plans) == 1:
            logger.debug(f"单域快捷路径: {domain_plans[0]['domain_name']}")

        return NodeResult(
            output=domain_plans,
            metadata={"max_domains": max_domains, "shortcut": len(domain_plans) == 1},
            node_id=context.node_id,
            node_type="query_analyzer",
        )
