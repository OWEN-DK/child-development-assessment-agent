"""L3 系统质量评分门面及计算器

包含 RegressionScoreCalculator、CostEfficiencyCalculator、ConfigStabilityCalculator 及 SystemScorer。
RuleComplianceCalculator 定义在 calculators/precision_recall.py。
"""

import asyncio
import math
from typing import Optional

from src.core.config.cache import ConfigCache
from src.schemas.rag_eval.metrics import (
    Layer3Metrics,
    MetricInput,
    MetricOutput,
    MetricResult,
)
from src.service.rag_eval.metrics.scoring.base import MetricCalculator
from src.service.rag_eval.metrics.scoring.registry import MetricRegistry


def _indicators(input_data: MetricInput) -> dict[str, float]:
    """从 MetricInput.details 提取指标字典，或返回默认空字典"""
    v = input_data.details.get("indicators", None) if input_data.details else None
    return v if isinstance(v, dict) else {}


class RegressionScoreCalculator(MetricCalculator):
    """回归评分：min(current/baseline, baseline/current) 加权均值，阈值 >= 0.9，无基线默认 1.0"""

    @property
    def name(self) -> str:
        return "regression_score"

    @property
    def layer(self) -> int:
        return 3

    @property
    def description(self) -> str:
        return "回归评分：与历史基线相比的稳定性"

    async def calculate(self, input_data: MetricInput) -> MetricOutput:
        threshold = await self._get_threshold()
        baseline = (input_data.details or {}).get("baseline_metrics", None)
        if not baseline:
            return MetricOutput(score=1.0, passed=True, threshold=threshold, details={"reason": "无历史基线，默认满分"})

        current = _indicators(input_data)
        ratios = []
        for k, cv in current.items():
            bv = baseline.get(k, cv) if isinstance(baseline, dict) else cv
            if bv > 0 and cv > 0:
                ratios.append(min(cv / bv, bv / cv))

        score = sum(ratios) / len(ratios) if ratios else 1.0
        return MetricOutput(score=round(score, 4), passed=score >= threshold, threshold=threshold,
                            details={"comparisons": len(ratios), "ratios": [round(r, 4) for r in ratios]})


class CostEfficiencyCalculator(MetricCalculator):
    """成本效率：质量综合分 / (token_cost * latency) 经 sigmoid 归一化到 [0,1]，阈值为可配置（默认 0.5）

    无成本数据（测试环境）时返回 1.0。
    """

    def __init__(self, config_cache: ConfigCache = None):
        super().__init__(config_cache)
        self._scale = 1000.0

    @property
    def name(self) -> str:
        return "cost_efficiency"

    @property
    def layer(self) -> int:
        return 3

    @property
    def description(self) -> str:
        return "成本效率：单位成本获得的质量"

    async def calculate(self, input_data: MetricInput) -> MetricOutput:
        threshold = await self._get_threshold()
        tc = input_data.cost_usd or 0.0
        lat = input_data.execution_time_ms or 0

        if tc == 0.0 and lat == 0:
            return MetricOutput(score=1.0, passed=True, threshold=threshold, details={"reason": "无成本数据，默认满分"})

        quality = (input_data.details or {}).get("quality_score", 0.5)
        raw = quality / (tc + 0.001) / (lat + 1)
        config = self._config_cache.get_latest_config()
        sf = float(config.get("rag.eval.threshold.cost_efficiency_scale", self._scale)) if config else self._scale
        score = 1.0 / (1.0 + math.exp(-raw * sf))

        return MetricOutput(score=round(score, 4), passed=score >= threshold, threshold=threshold,
                            details={"raw_efficiency": round(raw, 8), "scale_factor": sf})


class ConfigStabilityCalculator(MetricCalculator):
    """配置稳定性：1 - avg(|metric_new - metric_old| / metric_old)，阈值 >= 0.95，无历史默认 1.0"""

    @property
    def name(self) -> str:
        return "config_stability"

    @property
    def layer(self) -> int:
        return 3

    @property
    def description(self) -> str:
        return "配置稳定性：指标相对历史的变化幅度"

    async def calculate(self, input_data: MetricInput) -> MetricOutput:
        threshold = await self._get_threshold()
        prev = (input_data.details or {}).get("previous_metrics", None)
        if not prev:
            return MetricOutput(score=1.0, passed=True, threshold=threshold, details={"reason": "无历史指标数据，默认满分"})

        current = _indicators(input_data)
        deviations = []
        for k, cv in current.items():
            ov = prev.get(k, cv) if isinstance(prev, dict) else cv
            if ov > 0:
                deviations.append(min(abs(cv - ov) / ov, 1.0))

        avg_d = sum(deviations) / len(deviations) if deviations else 0.0
        score = 1.0 - avg_d
        return MetricOutput(score=round(max(0.0, score), 4), passed=score >= threshold, threshold=threshold,
                            details={"avg_deviation": round(avg_d, 4), "comparisons": len(deviations)})


class SystemScorer:
    """L3 系统质量评分器——并行计算全部四项 L3 指标返回 Layer3Metrics"""

    def __init__(self, registry: MetricRegistry):
        self._registry = registry

    async def score_all(self, input_data: MetricInput) -> Layer3Metrics:
        names = ["rule_compliance", "regression_score", "cost_efficiency", "config_stability"]
        results = await asyncio.gather(*[self._score(name, input_data) for name in names])
        return Layer3Metrics(
            rule_compliance=results[0], regression_score=results[1],
            cost_efficiency=results[2], config_stability=results[3],
        )

    async def score_single(self, name: str, input_data: MetricInput) -> MetricResult:
        return await self._score(name, input_data)

    async def _score(self, name: str, input_data: MetricInput) -> MetricResult:
        output = await self._registry.get_by_name(name).calculate(input_data)
        return MetricResult(value=output.score, passed=output.passed, threshold=output.threshold, details=output.details)
