"""L2 生成质量评分门面

聚合 FaithfulnessCalculator、AnswerRelevancyCalculator、GroundednessCalculator 三项指标。
"""

import asyncio

from src.schemas.rag_eval.metrics import Layer2Metrics, MetricInput, MetricScore
from src.service.rag_eval.metrics.scoring.registry import MetricRegistry


class GenerationScorer:
    """L2 生成质量评分器

    对单条 MetricInput 计算全部三项 L2 指标，返回 Layer2Metrics。
    """

    def __init__(self, registry: MetricRegistry):
        self._registry = registry

    async def score_all(self, input_data: MetricInput) -> Layer2Metrics:
        """并行计算全部三项 L2 指标"""
        l2_names = ["faithfulness", "answer_relevancy", "groundedness"]
        results = await asyncio.gather(
            *[self._calc_and_convert(name, input_data) for name in l2_names]
        )
        return Layer2Metrics(
            faithfulness=results[0],
            answer_relevancy=results[1],
            groundedness=results[2],
        )

    async def score_single(self, name: str, input_data: MetricInput) -> MetricScore:
        """计算单个 L2 指标并返回 MetricScore"""
        output = await self._registry.get_by_name(name).calculate(input_data)
        return MetricScore(
            value=output.score,
            passed=output.passed,
            threshold=output.threshold,
            details=output.details,
        )

    async def _calc_and_convert(self, name: str, input_data: MetricInput) -> MetricScore:
        """计算并转换为 MetricScore"""
        output = await self._registry.get_by_name(name).calculate(input_data)
        return MetricScore(
            value=output.score,
            passed=output.passed,
            threshold=output.threshold,
            details=output.details,
        )
