"""三层指标计算门面——ScoringFacade

对批量 MetricInput 计算完整三层指标并聚合为 RunMetrics。
"""

import asyncio
from datetime import datetime, timezone
from typing import Optional

from src.core.config.cache import ConfigCache
from src.schemas.rag_eval.metrics import (
    Layer1Metrics,
    Layer2Metrics,
    Layer3Metrics,
    MetricInput,
    MetricScore,
    RunMetrics,
)
from src.service.rag_eval.metrics.scoring.generation import GenerationScorer
from src.service.rag_eval.metrics.scoring.registry import MetricRegistry
from src.service.rag_eval.metrics.scoring.retrieval import RetrievalScorer
from src.service.rag_eval.metrics.scoring.system import SystemScorer


class ScoringFacade:
    """三层指标计算门面

    协调 L1/L2/L3 三个评分器，计算完整三层指标，聚合为 RunMetrics。
    """

    _DEFAULT_WEIGHTS = {"l1": 0.4, "l2": 0.4, "l3": 0.2}

    def __init__(
        self, registry: MetricRegistry, retrieval: RetrievalScorer,
        generation: GenerationScorer, system: SystemScorer,
        config_cache: Optional[ConfigCache] = None,
    ):
        self._registry = registry
        self._retrieval = retrieval
        self._generation = generation
        self._system = system
        self._config_cache = config_cache or ConfigCache.get_instance()

    async def calculate_all(self, results: list[MetricInput]) -> RunMetrics:
        """计算完整三层指标，按用例聚合后取均值"""
        if not results:
            return self._empty()

        all_l1, all_l2, all_l3 = [], [], []
        for rd in results:
            all_l1.append(await self._retrieval.score_all(rd))
            all_l2.append(await self._generation.score_all(rd))
            all_l3.append(await self._system.score_all(rd))

        weights = self._get_weights()
        l1 = self._agg_l1(all_l1)
        l2 = self._agg_l2(all_l2)
        l3 = self._agg_l3(all_l3)
        overall = weights["l1"] * self._layer_avg(l1) + weights["l2"] * self._layer_avg(l2) + weights["l3"] * self._layer_avg(l3)

        return RunMetrics(l1=l1, l2=l2, l3=l3, overall_score=round(overall, 4),
                          weights=weights, calculated_at=datetime.now(timezone.utc))

    async def calculate_layer(self, layer: int, results: list[MetricInput]) -> dict[str, MetricScore]:
        """计算单层指标，返回 {metric_name: MetricScore}"""
        if not results:
            return {}

        all_m: dict[str, list[MetricScore]] = {}
        for rd in results:
            if layer == 1:
                lm = await self._retrieval.score_all(rd)
            elif layer == 2:
                lm = await self._generation.score_all(rd)
            elif layer == 3:
                lm = await self._system.score_all(rd)
            else:
                continue
            self._collect(lm, all_m)

        averaged: dict[str, MetricScore] = {}
        for name, scores in all_m.items():
            avg_v = sum(s.value for s in scores) / len(scores)
            first = scores[0]
            averaged[name] = MetricScore(value=round(avg_v, 4), passed=all(s.passed for s in scores),
                                         threshold=first.threshold, details={"case_count": len(scores)})
        return averaged

    def _get_weights(self) -> dict[str, float]:
        config = self._config_cache.get_latest_config()
        if config:
            return {"l1": float(config.get("rag.eval.weight.l1", 0.4)),
                    "l2": float(config.get("rag.eval.weight.l2", 0.4)),
                    "l3": float(config.get("rag.eval.weight.l3", 0.2))}
        return dict(self._DEFAULT_WEIGHTS)

    def _agg_l1(self, ml: list[Layer1Metrics]) -> Layer1Metrics:
        return Layer1Metrics(context_precision=self._avg([m.context_precision for m in ml]),
                             context_recall=self._avg([m.context_recall for m in ml]),
                             noise_sensitivity=self._avg([m.noise_sensitivity for m in ml]),
                             mrr=self._avg([m.mrr for m in ml]),
                             ndcg=self._avg([m.ndcg for m in ml]))

    def _agg_l2(self, ml: list[Layer2Metrics]) -> Layer2Metrics:
        return Layer2Metrics(faithfulness=self._avg([m.faithfulness for m in ml]),
                             answer_relevancy=self._avg([m.answer_relevancy for m in ml]),
                             groundedness=self._avg([m.groundedness for m in ml]))

    def _agg_l3(self, ml: list[Layer3Metrics]) -> Layer3Metrics:
        return Layer3Metrics(rule_compliance=self._avg([m.rule_compliance for m in ml]),
                             regression_score=self._avg([m.regression_score for m in ml]),
                             cost_efficiency=self._avg([m.cost_efficiency for m in ml]),
                             config_stability=self._avg([m.config_stability for m in ml]))

    def _avg(self, scores: list[MetricScore]) -> MetricScore:
        if not scores:
            return MetricScore(value=0.0, passed=False, threshold=0.0, details={})
        avg_v = sum(s.value for s in scores) / len(scores)
        first = scores[0]
        return MetricScore(value=round(avg_v, 4), passed=all(s.passed for s in scores),
                           threshold=first.threshold, details={"case_count": len(scores)})

    def _layer_avg(self, lm) -> float:
        fields = [f for f in lm.__fields__ if isinstance(getattr(lm, f), MetricScore)]
        return sum(getattr(lm, f).value for f in fields) / len(fields) if fields else 0.0

    def _collect(self, layer_obj, all_m: dict[str, list[MetricScore]]) -> None:
        for field in layer_obj.__fields__:
            val = getattr(layer_obj, field)
            if isinstance(val, MetricScore):
                all_m.setdefault(field, []).append(val)

    def _empty(self) -> RunMetrics:
        es = MetricScore(value=0.0, passed=False, threshold=0.0, details={"reason": "无评估数据"})
        return RunMetrics(
            l1=Layer1Metrics(context_precision=es, context_recall=es, noise_sensitivity=es, mrr=es, ndcg=es),
            l2=Layer2Metrics(faithfulness=es, answer_relevancy=es, groundedness=es),
            l3=Layer3Metrics(rule_compliance=es, regression_score=es, cost_efficiency=es, config_stability=es),
            overall_score=0.0, weights=dict(self._DEFAULT_WEIGHTS), calculated_at=datetime.now(timezone.utc),
        )
