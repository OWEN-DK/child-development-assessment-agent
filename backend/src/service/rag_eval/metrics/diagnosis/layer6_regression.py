"""Layer 6: 回归检测

检测系统变更后的整体回归：全局指标退化、跨测试集一致性、成本效果变化。
"""

import time
from typing import Optional

from sqlalchemy import desc

from src.core.config.cache import ConfigCache
from src.models.rag_eval.enums import TestRunStatus
from src.models.rag_eval.test_run import TestRun
from src.repository.rag_eval.test_run_repository import TestRunRepository
from src.schemas.rag_eval.diagnosis import LayerIssue, LayerResult
from src.schemas.rag_eval.test_run import TestRunRead, TestRunResultItem
from src.service.rag_eval.metrics.diagnosis.diagnosis_utils import (
    calculate_layer_score, count_affected_cases, determine_layer_status)
from src.service.rag_eval.metrics.diagnosis.orchestrator import DiagnosisLayer

_REG_WARN = 0.05
_REG_CRIT = 0.10
_METRIC_FIELDS = ["overall_score", "overall_precision", "overall_recall",
                  "overall_f1", "overall_mrr", "overall_ndcg"]


class Layer6Regression(DiagnosisLayer):
    """回归检测诊断层——全局回归、交叉验证、成本效果评估"""

    def __init__(self, test_run_repository: Optional[TestRunRepository] = None,
                 config_cache: Optional[ConfigCache] = None):
        self._tr = test_run_repository or TestRunRepository()
        self._config_cache = config_cache or ConfigCache.get_instance()

    @property
    def layer_number(self) -> int: return 6
    @property
    def name(self) -> str: return "回归检测"

    async def diagnose(
        self, run_id: str, results: list[TestRunResultItem], run_data: TestRunRead
    ) -> LayerResult:
        start = time.time()
        baseline = await self._find_baseline(run_data)
        if baseline is None:
            return LayerResult(
                layer=self.layer_number, name=self.name, status="skip", score=1.0,
                issues=[LayerIssue(severity="info", category="no_baseline",
                         description="无基线数据，跳过回归检测", affected_items=[run_id],
                         suggestion="至少执行 2 次运行以启用回归检测")],
                details={"reason": "no_baseline"},
                execution_time_ms=int((time.time() - start) * 1000))

        issues: list[LayerIssue] = []
        issues.extend(self._check_global(baseline, run_data, run_id))
        issues.extend(self._check_cross(run_data, results))
        issues.extend(self._check_cost(baseline, run_data, run_id))

        total = len(results)
        return LayerResult(
            layer=self.layer_number, name=self.name,
            status=determine_layer_status(issues),
            score=calculate_layer_score(issues, total),
            total_cases=total,
            affected_cases=count_affected_cases(issues),
            issues=issues,
            details={"baseline_run_id": baseline.id, "total_results": total},
            execution_time_ms=int((time.time() - start) * 1000))

    def _check_global(self, baseline: TestRun, run_data: TestRunRead, run_id: str) -> list[LayerIssue]:
        issues: list[LayerIssue] = []
        reg_crit: list[str] = []
        reg_warn: list[str] = []

        for fn in _METRIC_FIELDS:
            bv = getattr(baseline, fn, None)
            cv = getattr(run_data, fn, None)
            if bv is None or cv is None or bv == 0:
                continue
            delta = (cv - bv) / bv
            if delta < -_REG_CRIT:
                reg_crit.append(f"{fn}({delta:.1%})")
            elif delta < -_REG_WARN:
                reg_warn.append(f"{fn}({delta:.1%})")

        reg = reg_crit + reg_warn
        if reg:
            issues.append(LayerIssue(
                severity="critical" if reg_crit else "warning",
                category="global_regression",
                description=f"全局指标回归: {', '.join(reg)}",
                affected_items=[run_id],
                suggestion="审查最近系统变更或配置调整"))
        return issues

    def _check_cross(self, run_data: TestRunRead, results: list[TestRunResultItem]) -> list[LayerIssue]:
        """跨测试集一致性检查"""
        issues: list[LayerIssue] = []
        ts_ids = run_data.test_set_ids or []
        if len(ts_ids) < 2:
            return issues

        rates: dict[str, float] = {}
        for tid in ts_ids:
            sr = [r for r in results if r.test_case_id and r.test_case_id.startswith(tid[:8])]
            if sr:
                rates[tid] = sum(1 for r in sr if r.passed) / len(sr)

        if len(rates) >= 2:
            vals = list(rates.values())
            if max(vals) - min(vals) > 0.3:
                issues.append(LayerIssue(
                    severity="warning", category="cross_validation",
                    description=f"测试集通过率差异过大: {min(vals):.0%}~{max(vals):.0%}",
                    affected_items=[tid for tid, v in rates.items() if v == min(vals)],
                    suggestion="检查低分测试集的用例质量"))
        return issues

    def _check_cost(self, baseline: TestRun, run_data: TestRunRead, run_id: str) -> list[LayerIssue]:
        issues: list[LayerIssue] = []
        bp = baseline.passed_test_cases / max(baseline.total_test_cases, 1)
        cp = run_data.passed_test_cases / max(run_data.total_test_cases, 1)

        if cp < bp - 0.05 and run_data.overall_score and baseline.overall_score:
            if run_data.overall_score < baseline.overall_score:
                issues.append(LayerIssue(
                    severity="warning", category="cost_effectiveness",
                    description="通过率与综合得分双降，系统存在回归",
                    affected_items=[run_id],
                    suggestion="评估系统变更投入产出比"))
        return issues

    async def _find_baseline(self, run_data: TestRunRead) -> Optional[TestRun]:
        all_runs = await self._tr.get_all(limit=50, order_by=desc(TestRun.created_at))
        current_set = set(run_data.test_set_ids or [])
        for run in all_runs:
            if run.id != run_data.id and run.status == TestRunStatus.COMPLETED:
                if set(run.test_set_ids or []) & current_set:
                    return run
        return None
