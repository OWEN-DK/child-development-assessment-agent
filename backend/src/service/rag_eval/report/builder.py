"""报告构建器——整合双轨评估结果为EvalReportData"""

import asyncio
from datetime import datetime, timezone

from src.repository.rag_eval.test_run_repository import TestRunRepository
from src.repository.rag_eval.test_run_result_repository import TestRunResultRepository
from src.repository.rag_eval.tuning_suggestion_repository import TuningSuggestionRepository
from src.schemas.rag_eval.diagnosis import DiagnosisResult, LayerIssue
from src.schemas.rag_eval.metrics import (
    Layer1Metrics, Layer2Metrics, Layer3Metrics, MetricScore, RunMetrics,
)
from src.schemas.rag_eval.report import (
    BadCaseEntry, DiagnosisSection, EvalReportData, MetricCard,
    OverallSummary, ScoringDashboard, TuningEntry,
)
from src.utils.exceptions import TestRunNotFoundException

_PASSED_THRESHOLD = 0.6
_METRIC_NAMES = {
    "l1": ["context_precision", "context_recall", "noise_sensitivity", "mrr", "ndcg"],
    "l2": ["faithfulness", "answer_relevancy", "groundedness"],
    "l3": ["rule_compliance", "regression_score", "cost_efficiency", "config_stability"],
}
_LAYER_NAMES = {1: "规则引擎校验", 2: "语义一致性校验", 3: "提示词质量校验",
                 4: "知识库质量校验", 5: "重排序效果校验", 6: "融合策略校验"}


class ReportBuilder:
    """整合双轨评估结果，构建报告数据"""

    def __init__(
        self,
        test_run_repository: TestRunRepository,
        test_run_result_repository: TestRunResultRepository,
        tuning_suggestion_repository: TuningSuggestionRepository,
        orm_mapper=None,
    ):
        self._run_repo = test_run_repository
        self._result_repo = test_run_result_repository
        self._suggestion_repo = tuning_suggestion_repository
        self._mapper = orm_mapper

    async def build(self, run_id: str) -> EvalReportData:
        """构建完整报告数据"""
        run = await self._run_repo.get_by_id(run_id)
        if run is None:
            raise TestRunNotFoundException(run_id)

        l1_json = run.l1_metrics_json or {}
        l2_json = run.l2_metrics_json or {}
        l3_json = run.l3_metrics_json or {}
        diag_json = run.diagnosis_json or {}

        # 并行查询失败结果和调优建议（两者无依赖关系）
        failed_results, suggestions = await asyncio.gather(
            self._result_repo.get_failed_results_by_run(run_id),
            self._suggestion_repo.get_by_run_id(run_id),
        )

        metrics = self._parse_metrics(l1_json, l2_json, l3_json, {
            "overall_score": run.overall_score or 0.0,
            "weights": {"l1": 0.4, "l2": 0.4, "l3": 0.2},
        })
        bad_cases = self._build_bad_cases(failed_results)
        tuning = self._build_tuning(suggestions)

        return EvalReportData(
            summary=self._build_summary(run, metrics, diag_json),
            scoring_dashboard=self._build_dashboard(l1_json, l2_json, l3_json),
            diagnosis_details=self._build_diagnosis(diag_json),
            bad_cases=bad_cases,
            tuning_suggestions=tuning,
        )

    def _parse_metrics(self, l1, l2, l3, all_json) -> RunMetrics:
        def _ms(d): return MetricScore(
            value=float(d.get("value", 0)), passed=bool(d.get("passed", False)),
            threshold=float(d.get("threshold", _PASSED_THRESHOLD)), details=d.get("details", {}))
        return RunMetrics(
            l1=Layer1Metrics(context_precision=_ms(l1.get("context_precision", {})),
                             context_recall=_ms(l1.get("context_recall", {})),
                             noise_sensitivity=_ms(l1.get("noise_sensitivity", {})),
                             mrr=_ms(l1.get("mrr", {})), ndcg=_ms(l1.get("ndcg", {}))),
            l2=Layer2Metrics(faithfulness=_ms(l2.get("faithfulness", {})),
                             answer_relevancy=_ms(l2.get("answer_relevancy", {})),
                             groundedness=_ms(l2.get("groundedness", {}))),
            l3=Layer3Metrics(rule_compliance=_ms(l3.get("rule_compliance", {})),
                             regression_score=_ms(l3.get("regression_score", {})),
                             cost_efficiency=_ms(l3.get("cost_efficiency", {})),
                             config_stability=_ms(l3.get("config_stability", {}))),
            overall_score=float(all_json.get("overall_score", 0.0)),
            weights=all_json.get("weights", {"l1": 0.4, "l2": 0.4, "l3": 0.2}),
            calculated_at=datetime.now(timezone.utc),
        )

    def _build_summary(self, run, metrics, diag_json) -> OverallSummary:
        def _avg(layer): 
            fields = [v for k, v in layer.__dict__.items() if isinstance(v, MetricScore)]
            return sum(v.value for v in fields) / len(fields) if fields else 0.0
        return OverallSummary(
            overall_score=metrics.overall_score,
            l1_score=_avg(metrics.l1), l2_score=_avg(metrics.l2), l3_score=_avg(metrics.l3),
            diagnosis_health=float(diag_json.get("overall_health", 0.0)) if isinstance(diag_json, dict) else 0.0,
            total_issues=diag_json.get("total_issues", 0) if isinstance(diag_json, dict) else 0,
            critical_issues=diag_json.get("critical_issues", 0) if isinstance(diag_json, dict) else 0,
            run_name=run.name, total_cases=run.total_test_cases or 0,
            passed_cases=run.passed_test_cases or 0,
            duration_ms=self._calc_duration_ms(run),
        )

    def _build_dashboard(self, l1, l2, l3) -> ScoringDashboard:
        def _cards(layer_json, names):
            result = []
            for name in names:
                d = (layer_json or {}).get(name, {}) if isinstance(layer_json, dict) else {}
                result.append(MetricCard(
                    name=name, value=float(d.get("value", 0)),
                    passed=bool(d.get("passed", False)),
                    threshold=float(d.get("threshold", _PASSED_THRESHOLD)),
                    details=d.get("details", {})))
            return result
        return ScoringDashboard(
            l1=_cards(l1, _METRIC_NAMES["l1"]),
            l2=_cards(l2, _METRIC_NAMES["l2"]),
            l3=_cards(l3, _METRIC_NAMES["l3"]),
        )

    def _build_diagnosis(self, diag_json) -> list[DiagnosisSection]:
        if not isinstance(diag_json, dict):
            return []
        sections = []
        for layer_num in range(1, 7):
            ld = diag_json.get(f"layer{layer_num}", {})
            if isinstance(ld, dict):
                issues = []
                for i in ld.get("issues", []):
                    if isinstance(i, dict):
                        issues.append(LayerIssue(
                            severity=i.get("severity", "info"), category=i.get("category", ""),
                            description=i.get("description", ""), affected_items=i.get("affected_items", []),
                            suggestion=i.get("suggestion")))
                sections.append(DiagnosisSection(
                    layer=layer_num, name=_LAYER_NAMES.get(layer_num, f"Layer {layer_num}"),
                    status=ld.get("status", "skip"), score=float(ld.get("score", 0)),
                    issues=issues, suggestions=ld.get("details", {}).get("suggestions", [])))
            else:
                sections.append(DiagnosisSection(
                    layer=layer_num, name=_LAYER_NAMES.get(layer_num, f"Layer {layer_num}"),
                    status="skip", score=0.0, issues=[], suggestions=[]))
        return sections

    def _build_bad_cases(self, bad_cases: list) -> list[BadCaseEntry]:
        entries = []
        for rc in bad_cases:
            if hasattr(rc, "__dict__"):
                entries.append(BadCaseEntry(
                    case_id=getattr(rc, "test_case_id", ""), query=getattr(rc, "query", ""),
                    expected_keywords=getattr(rc, "expected_knowledge_ids", []) or [],
                    actual_answer=getattr(rc, "actual_answer", None),
                    precision=getattr(rc, "precision", None),
                    recall=getattr(rc, "recall", None),
                    error_message=getattr(rc, "error_message", None)))
            else:
                entries.append(BadCaseEntry(
                    case_id=rc.get("test_case_id", ""), query=rc.get("query", ""),
                    expected_keywords=rc.get("expected_knowledge_ids", []) or [],
                    actual_answer=rc.get("actual_answer"),
                    precision=rc.get("precision"), recall=rc.get("recall"),
                    error_message=rc.get("error_message")))
        return entries

    def _build_tuning(self, suggestions: list) -> list[TuningEntry]:
        entries = []
        for s in suggestions:
            if hasattr(s, "__dict__"):
                entries.append(TuningEntry(
                    suggestion_id=getattr(s, "id", ""), category=getattr(s, "category", ""),
                    severity=getattr(s, "severity", "info"), title=getattr(s, "title", ""),
                    description=getattr(s, "description", ""),
                    current_value=getattr(s, "current_value", None),
                    suggested_value=getattr(s, "suggested_value", None),
                    expected_impact=getattr(s, "expected_impact", None),
                    conflict_with=getattr(s, "conflict_with", None)))
            else:
                entries.append(TuningEntry(
                    suggestion_id=s.get("id", ""), category=s.get("category", ""),
                    severity=s.get("severity", "info"), title=s.get("title", ""),
                    description=s.get("description", ""),
                    current_value=s.get("current_value"),
                    suggested_value=s.get("suggested_value"),
                    expected_impact=s.get("expected_impact"),
                    conflict_with=s.get("conflict_with")))
        severity_order = {"critical": 0, "warning": 1, "info": 2}
        entries.sort(key=lambda e: severity_order.get(e.severity, 99))
        return entries

    @staticmethod
    def _calc_duration_ms(run) -> int | None:
        if run.started_at and run.completed_at:
            delta = run.completed_at - run.started_at
            return int(delta.total_seconds() * 1000)
        return None
