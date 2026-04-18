"""统一调参建议引擎:协调三层诊断组件"""

import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from src.core.tuning.conflict_detector import ConflictDetector
from src.core.tuning.history_analyzer import HistoryAnalyzer
from src.core.tuning.llm_diagnoser import LLMDiagnoser
from src.core.tuning.rule_engine import RuleEngine
from src.schemas import TuningSuggestionResponse
from src.utils.logger import logger


class TuningSuggestionEngine:
    """统一调参建议引擎"""

    CACHE_TTL = 300

    def __init__(
        self,
        rule_engine: RuleEngine,
        history_analyzer: HistoryAnalyzer,
        llm_diagnoser: LLMDiagnoser,
        conflict_detector: ConflictDetector,
        test_run_repo=None,
    ):
        """初始化引擎"""
        self.rule_engine = rule_engine
        self.history_analyzer = history_analyzer
        self.llm_diagnoser = llm_diagnoser
        self.conflict_detector = conflict_detector
        self.test_run_repo = test_run_repo
        self._cache: Dict[str, tuple] = {}

    async def generate_suggestions(self, run_id: str) -> TuningSuggestionResponse:
        """生成调参建议(三层诊断)"""
        if run_id in self._cache:
            cached_response, cached_time = self._cache[run_id]
            if time.time() - cached_time < self.CACHE_TTL:
                logger.debug(f"缓存命中: run_id={run_id}")
                return cached_response
            else:
                logger.debug(f"缓存过期: run_id={run_id}")
                del self._cache[run_id]

        test_run = await self.test_run_repo.get_by_id(run_id)
        if not test_run:
            raise ValueError(f"测试运行不存在: {run_id}")

        metrics = {
            "overall_precision": test_run.overall_precision or 0,
            "overall_recall": test_run.overall_recall or 0,
            "overall_f1": test_run.overall_f1 or 0,
            "overall_mrr": test_run.overall_mrr or 0,
            "overall_ndcg": test_run.overall_ndcg or 0,
        }

        derived_metrics = await self._compute_derived_metrics(test_run)
        metrics.update(derived_metrics)

        rule_suggestions = await self.rule_engine.evaluate(metrics)
        logger.info(f"规则引擎生成 {len(rule_suggestions)} 条建议")

        history_refs = await self.history_analyzer.analyze(
            current_metrics=metrics,
            current_run_id=run_id,
        )
        logger.info(f"历史对比找到 {len(history_refs)} 条参考")

        llm_diag = await self.llm_diagnoser.diagnose(run_id)
        if llm_diag:
            logger.info(f"LLM 诊断生成 {len(llm_diag.recommendations)} 条建议")
            rule_suggestions.extend(llm_diag.recommendations)

        filtered_suggestions, conflict_count = self.conflict_detector.detect(
            rule_suggestions
        )

        priority_order = {"high": 0, "medium": 1, "low": 2}
        filtered_suggestions.sort(key=lambda s: priority_order.get(s.priority, 3))

        response = TuningSuggestionResponse(
            run_id=run_id,
            generated_at=datetime.now().isoformat(),
            rule_engine_suggestions=[
                s for s in filtered_suggestions if s.source == "rule_engine"
            ],
            history_references=history_refs,
            llm_diagnosis=llm_diag,
            conflict_filtered_count=conflict_count,
            total_suggestions=len(filtered_suggestions),
        )

        self._cache[run_id] = (response, time.time())

        return response

    async def _compute_derived_metrics(self, test_run: Any) -> Dict[str, float]:
        """计算派生指标"""
        results = await self.test_run_repo.get_results(test_run.id)
        if not results:
            return {
                "age_related_bad_case_ratio": 0.0,
                "complex_query_failure_rate": 0.0,
                "chunking_bad_case_ratio": 0.0,
                "avg_latency_ms": 0.0,
            }

        total = len(results)
        age_related_failures = 0
        complex_query_failures = 0
        chunking_failures = 0
        total_latency_ms = 0

        for result in results:
            total_latency_ms += getattr(result, "latency_ms", 0) or 0

            is_bad_case = (result.recall or 0) < 0.5 or (result.precision or 0) < 0.5
            if not is_bad_case:
                continue

            if getattr(result, "age_mismatch", False):
                age_related_failures += 1

            query_type = getattr(result, "query_type", "factual")
            if query_type in ("comparative", "procedural", "causal"):
                complex_query_failures += 1

            if getattr(result, "chunking_issue", False):
                chunking_failures += 1

        return {
            "age_related_bad_case_ratio": age_related_failures / total
            if total > 0
            else 0.0,
            "complex_query_failure_rate": complex_query_failures / total
            if total > 0
            else 0.0,
            "chunking_bad_case_ratio": chunking_failures / total if total > 0 else 0.0,
            "avg_latency_ms": total_latency_ms / total if total > 0 else 0.0,
        }
