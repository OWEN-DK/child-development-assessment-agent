"""L1 检索质量评分门面

聚合 PrecisionAtK、ContextRecall、NoiseSensitivity、MRR、NDCG 五项指标。
"""

import asyncio

from src.schemas.rag_eval.metrics import Layer1Metrics, MetricInput, MetricResult
from src.service.rag_eval.metrics.scoring.registry import MetricRegistry


class RetrievalScorer:
    """L1 检索质量评分器

    对单条 MetricInput 计算全部五项 L1 指标，返回 Layer1Metrics。
    """

    def __init__(self, registry: MetricRegistry):
        self._registry = registry

    async def score_all(self, input_data: MetricInput) -> Layer1Metrics:
        """并行计算全部五项 L1 指标"""
        l1_names = ["context_precision", "context_recall", "noise_sensitivity", "mrr", "ndcg"]
        results = await asyncio.gather(
            *[self._calc_and_convert(name, input_data) for name in l1_names]
        )
        return Layer1Metrics(
            context_precision=results[0],
            context_recall=results[1],
            noise_sensitivity=results[2],
            mrr=results[3],
            ndcg=results[4],
        )

    async def score_single(self, name: str, input_data: MetricInput) -> MetricResult:
        """计算单个 L1 指标并返回 MetricResult"""
        output = await self._registry.get_by_name(name).calculate(input_data)
        return MetricResult(
            value=output.score,
            passed=output.passed,
            threshold=output.threshold,
            details=output.details,
        )

    async def _calc_and_convert(self, name: str, input_data: MetricInput) -> MetricResult:
        """计算并转换为 MetricResult"""
        output = await self._registry.get_by_name(name).calculate(input_data)
        return MetricResult(
            value=output.score,
            passed=output.passed,
            threshold=output.threshold,
            details=output.details,
        )
