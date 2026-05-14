"""查询分析节点

LLM 调用识别查询涉及的域，输出域执行计划。
"""
from typing import Any

from src.core.pipeline.base_node import BaseNodeExecutor
from src.core.pipeline.llm_helper import call_llm_json
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

        model = context.config.get("model", "qwen-turbo")
        max_domains = context.config.get("max_domains", 5)
        min_confidence = context.config.get("min_confidence", 0.6)
        domain_keywords = context.config.get("domain_keywords", {})

        # 如果没有配置域信息，返回默认域
        if not domain_keywords:
            domain_plans = [{
                "domain_id": "default",
                "domain_name": "默认域",
                "knowledge_base_id": context.config.get("default_kb_id", ""),
                "confidence": 1.0,
                "reason": "未配置域信息，默认路由",
            }]
            return NodeResult(
                output=domain_plans,
                metadata={"max_domains": max_domains, "shortcut": True},
                node_id=context.node_id,
                node_type="query_analyzer",
            )

        # 使用 LLM 分析查询涉及的域
        domain_list = "\n".join([
            f"- {did}: {info.get('name', did)} (关键词: {', '.join(info.get('keywords', []))})"
            for did, info in domain_keywords.items()
        ])

        system_prompt = f"""你是一个查询意图分析专家。根据用户查询，判断它涉及哪些知识域。

可用的域列表：
{domain_list}

返回 JSON 数组，每个元素包含：
- domain_id: 域 ID
- domain_name: 域名称
- confidence: 置信度 (0-1)
- reason: 判断理由

只返回置信度 >= {min_confidence} 的域，最多返回 {max_domains} 个。"""

        try:
            result = await call_llm_json(
                prompt=query,
                model=model,
                temperature=0.1,
                system_prompt=system_prompt,
            )

            if isinstance(result, list):
                domain_plans = [
                    {
                        "domain_id": d.get("domain_id", ""),
                        "domain_name": d.get("domain_name", ""),
                        "knowledge_base_id": domain_keywords.get(d.get("domain_id", ""), {}).get("kb_id", ""),
                        "confidence": d.get("confidence", 0),
                        "reason": d.get("reason", ""),
                    }
                    for d in result
                    if d.get("confidence", 0) >= min_confidence
                ][:max_domains]
            else:
                domain_plans = []

        except Exception as e:
            logger.warning(f"查询分析失败: {e}")
            domain_plans = []

        # 如果没有识别到域，使用第一个可用域
        if not domain_plans and domain_keywords:
            first_id = next(iter(domain_keywords))
            domain_plans = [{
                "domain_id": first_id,
                "domain_name": domain_keywords[first_id].get("name", first_id),
                "knowledge_base_id": domain_keywords[first_id].get("kb_id", ""),
                "confidence": 0.5,
                "reason": "LLM 未识别到明确域，使用默认域",
            }]

        # 单域快捷路径
        shortcut = len(domain_plans) == 1
        if shortcut:
            logger.debug(f"单域快捷路径: {domain_plans[0]['domain_name']}")

        return NodeResult(
            output=domain_plans,
            metadata={
                "max_domains": max_domains,
                "shortcut": shortcut,
                "domain_count": len(domain_plans),
            },
            node_id=context.node_id,
            node_type="query_analyzer",
        )
