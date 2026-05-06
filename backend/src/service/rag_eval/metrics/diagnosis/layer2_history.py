"""Layer 2: 历史对比

与历史基线对比，检测异常退化：核心指标退化（>5% 警告，>10% 严重）、
新增失败用例、回答质量变化。
"""

import time
from typing import Optional

from sqlalchemy import desc

from src.core.config.cache import ConfigCache
from src.models.rag_eval.enums import TestRunStatus
from src.models.rag_eval.test_run import TestRun
from src.repository.rag_eval.test_run_repository import TestRunRepository
from src.repository.rag_eval.test_run_result_repository import TestRunResultRepository
from src.schemas.rag_eval.diagnosis import LayerIssue, LayerResult
from src.schemas.rag_eval.test_run import TestRunRead, TestRunResultItem
from src.service.rag_eval.metrics.diagnosis.diagnosis_utils import (
    calculate_layer_score, count_affected_cases, determine_layer_status)
from src.service.rag_eval.metrics.diagnosis.orchestrator import DiagnosisLayer

_DEG_WARN = 0.05
_DEG_CRIT = 0.10
_METRIC_FIELDS = ["overall_score", "overall_precision", "overall_recall",
                  "overall_f1", "overall_mrr", "overall_ndcg"]


class Layer2History(DiagnosisLayer):
    """历史对比诊断层——查找基线运行对比指标退化和失败变化"""

    def __init__(self, test_run_repository: Optional[TestRunRepository] = None,
                 test_run_result_repository: Optional[TestRunResultRepository] = None,
                 config_cache: Optional[ConfigCache] = None):
        self._tr = test_run_repository or TestRunRepository()
        self._trr = test_run_result_repository or TestRunResultRepository()
        self._config_cache = config_cache or ConfigCache.get_instance()

    @property
    def layer_number(self) -> int: return 2
    @property
    def name(self) -> str: return "历史对比"

    async def diagnose(
        self, run_id: str, results: list[TestRunResultItem], run_data: TestRunRead
    ) -> LayerResult:
        start = time.time()
        baseline = await self._find_baseline(run_data)
        if baseline is None:
            return LayerResult(
                layer=self.layer_number, name=self.name, status="skip", score=1.0,
                issues=[LayerIssue(severity="info", category="no_baseline",
                         description="无历史基线数据，跳过历史对比", affected_items=[run_id],
                         suggestion="执行多轮运行以建立基线")],
                details={"reason": "no_baseline"},
                execution_time_ms=int((time.time() - start) * 1000))

        issues: list[LayerIssue] = []
        issues.extend(self._compare_metrics(baseline, run_data, run_id))
        issues.extend(await self._compare_failures(baseline.id, results))

        total = len(results)
        return LayerResult(
            layer=self.layer_number, name=self.name,
            status=determine_layer_status(issues),
            score=calculate_layer_score(issues, total),
            total_cases=total,
            affected_cases=count_affected_cases(issues),
            issues=issues,
            details={"baseline_run_id": baseline.id, "baseline_run_name": baseline.name,
                     "current_total": total},
            execution_time_ms=int((time.time() - start) * 1000))

    def _compare_metrics(self, baseline: TestRun, run_data: TestRunRead, run_id: str) -> list[LayerIssue]:
        issues: list[LayerIssue] = []
        for fn in _METRIC_FIELDS:
            bv = getattr(baseline, fn, None)
            cv = getattr(run_data, fn, None)
            if bv is None or cv is None or bv == 0:
                continue
            delta = (cv - bv) / bv
            if delta < -_DEG_CRIT:
                issues.append(LayerIssue(
                    severity="critical", category="metric_degradation",
                    description=f"{fn}: {bv:.4f}→{cv:.4f}（{delta:.1%}）",
                    affected_items=[run_id], suggestion=f"检查 {fn} 退化原因"))
            elif delta < -_DEG_WARN:
                issues.append(LayerIssue(
                    severity="warning", category="metric_degradation",
                    description=f"{fn}: {bv:.4f}→{cv:.4f}（{delta:.1%}）",
                    affected_items=[run_id], suggestion=f"监控 {fn} 趋势"))
        return issues

    async def _compare_failures(self, baseline_run_id: str,
                                 current_results: list[TestRunResultItem]) -> list[LayerIssue]:
        issues: list[LayerIssue] = []
        br = await self._trr.get_by_run_id(baseline_run_id, limit=5000)
        b_passed = {r.test_case_id for r in br if r.passed}
        c_failed = {r.test_case_id for r in current_results if not r.passed}

        new_fail = b_passed & c_failed
        if new_fail:
            issues.append(LayerIssue(
                severity="critical" if len(new_fail) > 3 else "warning",
                category="new_failures",
                description=f"新增 {len(new_fail)} 个失败用例（之前通过）",
                affected_items=list(new_fail),
                suggestion="检查新增失败用例的检索/生成流程"))
        return issues

    async def _find_baseline(self, run_data: TestRunRead) -> Optional[TestRun]:
        all_runs = await self._tr.get_all(limit=50, order_by=desc(TestRun.created_at))
        current_set = set(run_data.test_set_ids or [])
        for run in all_runs:
            if run.id != run_data.id and run.status == TestRunStatus.COMPLETED:
                if set(run.test_set_ids or []) & current_set:
                    return run
        return None
