"""
查询路由器 - 智能分类查询类型并路由到合适的检索引擎
"""

import json
import logging
import re
from enum import Enum
from typing import Tuple

from src.config import settings
from src.core.llm.factory import LLMFramework, LLMServiceFactory, LLMServiceFactoryCompat
from src.schemas import LLMMessage, LLMRequest, QueryClassification, QueryType

logger = logging.getLogger(__name__)


class QueryRouter:
    """
    查询路由器

    分类策略:
    1. 规则优先：快速匹配关键词型查询
    2. LLM 辅助：处理模糊和复杂查询
    3. 置信度阈值：低于阈值走默认路径
    """

    # 简单查询的正则模式
    SIMPLE_PATTERNS = [
        r".*有哪些.*",  # "注意力训练有哪些方法？"
        r".*是什么.*",  # "什么是感统失调？"
        r".*怎么办.*",  # "孩子注意力不集中怎么办？"
        r".*怎么做.*",  # "前庭觉训练怎么做？"
        r".*方法.*",  # "提高专注力的方法"
        r".*技巧.*",  # "亲子沟通技巧"
    ]

    # 复杂查询的关键字（单个即触发，从 orchestrator 对齐）
    COMPLEX_KEYWORDS = [
        "分析",
        "评估",
        "对比",
        "关系",
        "影响",
        "原因",
        "综合",
        "多维度",
        "几个方面",
        "生成报告",
        "区别",
        "差异",
        "比较",
        "如何",
        "为什么",
    ]

    # 长度阈值：超过此长度视为复杂查询
    COMPLEX_LENGTH_THRESHOLD = 20

    def __init__(self):
        self.llm_available = settings.query_router_llm_enabled and bool(
            settings.dashscope_api_key
        )

    def classify(self, query: str) -> QueryClassification:
        """
        分类查询类型（同步版本，LLM 分类使用同步调用）

        Args:
            query: 用户查询

        Returns:
            QueryClassification: 查询分类结果
        """
        # 1. 规则分类（快速路径）
        rule_result = self._regex_classify(query)
        if (
            rule_result
            and rule_result.confidence >= settings.query_router_confidence_threshold
        ):
            return rule_result

        # 2. LLM 分类（可选，处理模糊情况）
        if self.llm_available:
            llm_result = self._llm_classify_sync(query)
            # 融合规则和 LLM 结果
            return self._fuse_results(rule_result, llm_result)

        # 3. 默认返回
        return QueryClassification(
            query_type=QueryType.DEFAULT,
            confidence=0.5,
            reasoning="未命中规则且 LLM 未启用",
        )

    async def classify_async(self, query: str) -> QueryClassification:
        """
        分类查询类型（异步版本）

        Args:
            query: 用户查询

        Returns:
            QueryClassification: 查询分类结果
        """
        # 1. 规则分类（快速路径）
        rule_result = self._regex_classify(query)
        if (
            rule_result
            and rule_result.confidence >= settings.query_router_confidence_threshold
        ):
            return rule_result

        # 2. LLM 分类（可选，处理模糊情况）
        if self.llm_available:
            llm_result = await self._llm_classify(query)
            # 融合规则和 LLM 结果
            return self._fuse_results(rule_result, llm_result)

        # 3. 默认返回
        return QueryClassification(
            query_type=QueryType.DEFAULT,
            confidence=0.5,
            reasoning="未命中规则且 LLM 未启用",
        )

    def _regex_classify(self, query: str) -> QueryClassification | None:
        """基于规则的分类（增强：全局匹配、归一化）"""
        # 查询归一化（去空格、去语气词）
        normalized_query = self._normalize_query(query)

        # 检查是否为简单查询（使用 re.search 全局匹配）
        for pattern in self.SIMPLE_PATTERNS:
            if re.search(pattern, normalized_query):
                return QueryClassification(
                    query_type=QueryType.SIMPLE,
                    confidence=0.85,
                    reasoning=f"匹配简单查询模式：{pattern}",
                )

        # 检查是否包含复杂查询关键字（单个即触发）
        for kw in self.COMPLEX_KEYWORDS:
            if kw in normalized_query:
                return QueryClassification(
                    query_type=QueryType.COMPLEX,
                    confidence=0.8,
                    reasoning=f"包含复杂查询关键字：{kw}",
                )

        # 长度阈值
        if len(query) > self.COMPLEX_LENGTH_THRESHOLD:
            return QueryClassification(
                query_type=QueryType.COMPLEX,
                confidence=0.65,
                reasoning=f"查询长度 {len(query)} > {self.COMPLEX_LENGTH_THRESHOLD}",
            )

        return None

    def _normalize_query(self, query: str) -> str:
        """查询归一化（去空格、去语气词）"""
        # 去除首尾空格
        query = query.strip()

        # 去除常见语气词
        query = re.sub(r"^[请问，。！？嗯啊哦]+", "", query)

        return query

    async def _llm_classify(self, query: str) -> QueryClassification:
        """使用 LLM 辅助分类（异步版本，增强：JSON 校验 + 重试）"""
        prompt = f"""
你是一个查询分类专家。请判断以下查询属于哪种类型：

查询类型定义：
- SIMPLE: 简单查询，包含明确关键词，单步检索可解决
  示例："注意力训练的方法有哪些？"、"3 岁孩子身高标准是多少？"
  
- COMPLEX: 复杂查询，需要多步推理、跨文档关联或综合分析
  示例："分析小明在前庭觉、精细动作、社交三个维度的发展情况，生成综合评估报告"
  
- DEFAULT: 无法明确分类的查询

查询："{query}"

请**只返回 JSON 格式**，不要有任何其他文本：
{{
    "query_type": "SIMPLE|COMPLEX|DEFAULT",
    "confidence": 0.0-1.0,
    "reasoning": "分类理由"
}}
"""
        # 重试机制
        for attempt in range(settings.query_router_llm_max_retries):
            try:
                # 使用工厂创建 LLM 实例
                llm = LLMServiceFactoryCompat.create(
                    framework=LLMFramework.LLAMAINDEX,
                    model_name=settings.model_query_classification,
                    scenario="query_classification",
                    temperature=0.2,
                )

                messages = [
                    LLMMessage(
                        role="system",
                        content="你是一个查询分类专家，负责判断用户查询的复杂度。",
                    ),
                    LLMMessage(role="user", content=prompt),
                ]

                response = await llm.chat(
                    LLMRequest(
                        messages=messages,
                        model_name=settings.model_query_classification,
                        temperature=0.2,
                        max_tokens=128,
                        scenario="query_classification",
                        prompt_key="query_classification",
                    )
                )
                response_text = response.content

                # 解析 LLM 返回的 JSON（带格式校验）
                json_match = re.search(r"\{.*\}", response_text, re.DOTALL)
                if not json_match:
                    raise ValueError(f"LLM 返回非 JSON 格式：{response_text[:100]}")

                json_str = json_match.group()
                result = json.loads(json_str)

                # 字段校验
                if "query_type" not in result or "confidence" not in result:
                    raise ValueError(f"LLM 返回缺少必要字段：{result}")

                # 枚举值校验
                if result["query_type"] not in ["SIMPLE", "COMPLEX", "DEFAULT"]:
                    raise ValueError(f"无效的 query_type: {result['query_type']}")

                return QueryClassification(
                    query_type=QueryType(result["query_type"].lower()),
                    confidence=float(result["confidence"]),
                    reasoning=result.get("reasoning", ""),
                )

            except Exception as e:
                logger.warning(f"LLM 分类失败（第{attempt + 1}次）: {e}")
                if attempt == settings.query_router_llm_max_retries - 1:
                    # 最后一次重试失败，降级到规则结果
                    logger.error("LLM 分类所有重试失败，返回 DEFAULT 类型")
                    return QueryClassification(
                        query_type=QueryType.DEFAULT,
                        confidence=0.5,
                        reasoning=f"LLM 分类异常：{str(e)}",
                    )

    def _llm_classify_sync(self, query: str) -> QueryClassification:
        """使用 LLM 辅助分类（同步版本，用于同步 classify 方法）"""
        import asyncio

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            # Already in async context, use sync fallback or skip LLM
            logger.warning(
                "LLM classify called from async context via sync method, skipping LLM"
            )
            return QueryClassification(
                query_type=QueryType.DEFAULT,
                confidence=0.5,
                reasoning="同步方法在异步上下文中调用，跳过 LLM 分类",
            )
        else:
            return asyncio.run(self._llm_classify(query))

    def _fuse_results(
        self, rule_result: QueryClassification | None, llm_result: QueryClassification
    ) -> QueryClassification:
        """融合规则和 LLM 结果"""
        if not rule_result:
            return llm_result

        # 规则置信度高，优先采用规则结果
        if rule_result.confidence >= 0.85:
            return rule_result

        # 置信度接近，采用 LLM 结果
        if abs(rule_result.confidence - llm_result.confidence) < 0.1:
            return llm_result

        # 否则采用置信度高的
        return (
            rule_result
            if rule_result.confidence > llm_result.confidence
            else llm_result
        )
