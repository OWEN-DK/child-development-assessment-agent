"""指标计算引擎门面

统一对外接口，协调 L1/L2/L3 和跨域指标的计算。
使用 asyncio.gather 并行执行各层指标计算。
综合得分权重可配置（从 ConfigCache 读取，否则使用默认权重）。
"""
import asyncio
from typing import Any, Optional

from src.schemas.rag_eval.metrics import (
    CrossDomainMetrics,
    LayerMetrics,
    MetricScore,
    RunMetrics,
)
from src.service.rag_eval.metrics.scoring.calculators.cross_domain_calc import (
    ConflictDetectionRateCalc,
    CrossDomainCoverageCalc,
    DomainActivationAccCalc,
    E2ELatencyCalc,
)
from src.utils.logger import logger

# 默认权重配置
DEFAULT_WEIGHTS = {
    "l1": 0.4,
    "l2": 0.4,
    "l3": 0.15,
    "cross_domain": 0.05,
}


class MetricEngineFacade:
    """指标计算引擎门面

    统一对外接口，并行调度各层指标计算器。
    处理 N/A 指标的权重重新分配。
    """

    def __init__(self, config_cache: Optional[Any] = None):
        self._config_cache = config_cache
        self._domain_activation_calc = DomainActivationAccCalc()
        self._cross_coverage_calc = CrossDomainCoverageCalc()
        self._conflict_detection_calc = ConflictDetectionRateCalc()
        self._latency_calc = E2ELatencyCalc()

    async def calculate_all(
        self,
        results: list[dict[str, Any]],
        l1_metrics: Optional[list[MetricScore]] = None,
        l2_metrics: Optional[list[MetricScore]] = None,
        l3_metrics: Optional[list[MetricScore]] = None,
    ) -> RunMetrics:
        """计算全部指标（L1/L2/L3 + 跨域）

        Args:
            results: 用例执行结果列表，每项含 test_case + result
            l1_metrics: 预计算的 L1 检索层指标（如已计算则跳过）
            l2_metrics: 预计算的 L2 生成层指标
            l3_metrics: 预计算的 L3 系统层指标

        Returns:
            RunMetrics 包含各层加权平均分和综合得分
        """
        # 并行计算跨域指标
        cross_domain_task = self.calculate_cross_domain(results)

        # 跨域指标独立计算（不依赖 L1/L2/L3）
        cross_domain_metrics = await cross_domain_task

        # 构建层级指标
        l1 = self._build_layer("l1", l1_metrics or [])
        l2 = self._build_layer("l2", l2_metrics or [])
        l3 = self._build_layer("l3", l3_metrics or [])

        # 计算综合得分（N/A 指标从分母排除）
        overall = self._compute_overall(l1, l2, l3, cross_domain_metrics)

        return RunMetrics(
            l1=l1,
            l2=l2,
            l3=l3,
            cross_domain=cross_domain_metrics,
            overall_score=round(overall, 4),
        )

    async def calculate_cross_domain(
        self, inputs: list[dict[str, Any]]
    ) -> Optional[CrossDomainMetrics]:
        """计算跨域扩展指标

        并行执行 4 项计算器，如果全部 N/A 则返回 None。
        """
        if not inputs:
            return None

        # 并行执行
        results = await asyncio.gather(
            asyncio.to_thread(self._domain_activation_calc.calculate, inputs),
            asyncio.to_thread(self._cross_coverage_calc.calculate, inputs),
            asyncio.to_thread(self._conflict_detection_calc.calculate, inputs),
            asyncio.to_thread(self._latency_calc.calculate, inputs),
            return_exceptions=True,
        )

        scores = []
        for r in results:
            if isinstance(r, Exception):
                logger.warning(f"跨域指标计算异常: {r}")
                scores.append(None)
            else:
                scores.append(r)

        # 全部 N/A → 返回 None
        if all(s is None or (s and s.score < 0) for s in scores):
            return None

        def _score_val(s: Optional[MetricScore]) -> float:
            if s is None or s.score < 0:
                return 0.0
            return s.score

        return CrossDomainMetrics(
            domain_activation_accuracy=_score_val(scores[0]),
            cross_domain_coverage=_score_val(scores[1]),
            conflict_detection_rate=_score_val(scores[2]),
            e2e_latency_p95=_score_val(scores[3]),
        )

    def _build_layer(
        self, layer_id: str, metrics: list[MetricScore]
    ) -> LayerMetrics:
        """构建层级指标

        计算该层各指标的加权平均分。
        """
        if not metrics:
            return LayerMetrics(layer=layer_id, scores=[], avg_score=0.0)

        total_weight = sum(m.weight for m in metrics)
        if total_weight == 0:
            avg = 0.0
        else:
            avg = sum(m.score * m.weight for m in metrics) / total_weight

        return LayerMetrics(
            layer=layer_id,
            scores=list(metrics),
            avg_score=round(avg, 4),
        )

    def _compute_overall(
        self,
        l1: LayerMetrics,
        l2: LayerMetrics,
        l3: LayerMetrics,
        cross_domain: Optional[CrossDomainMetrics],
    ) -> float:
        """计算综合得分

        公式：L1 × 0.4 + L2 × 0.4 + L3 × 0.15 + cross_domain × 0.05
        N/A 指标从分母排除，权重重新归一化。
        """
        weights = self._get_weights()

        total_weight = 0.0
        weighted_sum = 0.0

        # L1
        if l1.avg_score >= 0:
            w = weights["l1"]
            total_weight += w
            weighted_sum += l1.avg_score * w

        # L2
        if l2.avg_score >= 0:
            w = weights["l2"]
            total_weight += w
            weighted_sum += l2.avg_score * w

        # L3
        if l3.avg_score >= 0:
            w = weights["l3"]
            total_weight += w
            weighted_sum += l3.avg_score * w

        # Cross-domain
        if cross_domain is not None:
            w = weights["cross_domain"]
            cd_scores = [
                cross_domain.domain_activation_accuracy,
                cross_domain.cross_domain_coverage,
                cross_domain.conflict_detection_rate,
                cross_domain.e2e_latency_p95,
            ]
            valid_cd = [s for s in cd_scores if s >= 0]
            if valid_cd:
                cd_avg = sum(valid_cd) / len(valid_cd)
                total_weight += w
                weighted_sum += cd_avg * w

        return weighted_sum / total_weight if total_weight > 0 else 0.0

    def _get_weights(self) -> dict[str, float]:
        """获取权重配置（优先从 ConfigCache 读取，否则用默认）"""
        if self._config_cache:
            try:
                return {
                    "l1": float(self._config_cache.get_value("rag.eval.weight.l1", "0.4")),
                    "l2": float(self._config_cache.get_value("rag.eval.weight.l2", "0.4")),
                    "l3": float(self._config_cache.get_value("rag.eval.weight.l3", "0.15")),
                    "cross_domain": float(self._config_cache.get_value("rag.eval.weight.cross_domain", "0.05")),
                }
            except Exception:
                pass
        return DEFAULT_WEIGHTS.copy()
