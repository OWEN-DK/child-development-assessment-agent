"""Phase 7 指标计算器单元测试"""
import pytest
from src.service.rag_eval.metrics.scoring.calculators.cross_domain_calc import (
    DomainActivationAccCalc,
    CrossDomainCoverageCalc,
    ConflictDetectionRateCalc,
    E2ELatencyCalc,
)
from src.service.rag_eval.metrics.facade import MetricEngineFacade


def _make_input(relevant_domains=None, expected_conflicts=None, domain_results=None,
               execution_time_ms=None, error_message=None):
    """构建计算器输入"""
    test_case = {}
    if relevant_domains is not None:
        test_case["relevant_domains"] = relevant_domains
    if expected_conflicts is not None:
        test_case["expected_conflicts"] = expected_conflicts
    result = {}
    if domain_results is not None:
        result["domain_results_json"] = domain_results
    if execution_time_ms is not None:
        result["execution_time_ms"] = execution_time_ms
    if error_message is not None:
        result["error_message"] = error_message
    return {"test_case": test_case, "result": result}


# ═══ 域激活准确率 ═══

class TestDomainActivationAccCalc:

    def test_all_domains_activated(self):
        calc = DomainActivationAccCalc()
        inputs = [_make_input(
            relevant_domains=["cardiology", "pharmacy"],
            domain_results={
                "cardiology": {"activated": True, "contribution": 0.8},
                "pharmacy": {"activated": True, "contribution": 0.6},
            },
        )]
        score = calc.calculate(inputs)
        assert score.score == 1.0
        assert score.passed is True

    def test_partial_activation(self):
        calc = DomainActivationAccCalc()
        inputs = [_make_input(
            relevant_domains=["cardiology", "pharmacy", "endocrinology"],
            domain_results={
                "cardiology": {"activated": True, "contribution": 0.8},
                "pharmacy": {"activated": False, "contribution": 0},
            },
        )]
        score = calc.calculate(inputs)
        assert score.score == pytest.approx(1.0 / 3, 0.01)
        assert score.passed is False

    def test_no_relevant_domains_returns_na(self):
        calc = DomainActivationAccCalc()
        inputs = [_make_input(
            relevant_domains=[],
            domain_results={"cardiology": {"activated": True}},
        )]
        score = calc.calculate(inputs)
        assert score.score == -1
        assert score.passed is None


# ═══ 跨域覆盖率 ═══

class TestCrossDomainCoverageCalc:

    def test_full_coverage(self):
        calc = CrossDomainCoverageCalc()
        inputs = [_make_input(
            relevant_domains=["cardiology", "pharmacy"],
            domain_results={
                "cardiology": {"contribution": 0.8},
                "pharmacy": {"contribution": 0.6},
            },
        )]
        score = calc.calculate(inputs)
        assert score.score == 1.0

    def test_partial_coverage(self):
        calc = CrossDomainCoverageCalc()
        inputs = [
            _make_input(
                relevant_domains=["cardiology", "pharmacy"],
                domain_results={
                    "cardiology": {"contribution": 0.8},
                    "pharmacy": {"contribution": 0},
                },
            ),
            _make_input(
                relevant_domains=["cardiology"],
                domain_results={
                    "cardiology": {"contribution": 0.5},
                },
            ),
        ]
        score = calc.calculate(inputs)
        assert score.score == pytest.approx(2.0 / 3, 0.01)

    def test_empty_relevant_returns_na(self):
        calc = CrossDomainCoverageCalc()
        inputs = [_make_input(relevant_domains=[])]
        score = calc.calculate(inputs)
        assert score.score == -1
        assert score.passed is None


# ═══ 冲突检测率 ═══

class TestConflictDetectionRateCalc:

    def test_all_conflicts_detected(self):
        calc = ConflictDetectionRateCalc()
        inputs = [_make_input(
            expected_conflicts=[
                {"statement_a": "A", "source_a": "src1", "statement_b": "B", "source_b": "src2"},
            ],
            domain_results={
                "cardiology": {"conflicts": [{"type": "drug_interaction"}]},
            },
        )]
        score = calc.calculate(inputs)
        assert score.score == 1.0

    def test_no_expected_conflicts_returns_na(self):
        calc = ConflictDetectionRateCalc()
        inputs = [_make_input(expected_conflicts=[])]
        score = calc.calculate(inputs)
        assert score.score == -1
        assert score.passed is None

    def test_zero_detection_rate(self):
        calc = ConflictDetectionRateCalc()
        inputs = [_make_input(
            expected_conflicts=[
                {"statement_a": "A", "source_a": "s1", "statement_b": "B", "source_b": "s2"},
                {"statement_a": "C", "source_a": "s3", "statement_b": "D", "source_b": "s4"},
            ],
            domain_results={"cardiology": {"conflicts": []}},
        )]
        score = calc.calculate(inputs)
        assert score.score == 0.0


# ═══ 端到端延迟 ═══

class TestE2ELatencyCalc:

    def test_p95_computation(self):
        calc = E2ELatencyCalc()
        inputs = [
            _make_input(execution_time_ms=100),
            _make_input(execution_time_ms=200),
            _make_input(execution_time_ms=300),
            _make_input(execution_time_ms=400),
            _make_input(execution_time_ms=500),
        ]
        score = calc.calculate(inputs)
        assert score.passed is True
        assert score.score >= 0

    def test_high_latency_low_score(self):
        calc = E2ELatencyCalc()
        inputs = [_make_input(execution_time_ms=8000)]
        score = calc.calculate(inputs)
        assert score.score < 0.5

    def test_empty_inputs_returns_na(self):
        calc = E2ELatencyCalc()
        score = calc.calculate([])
        assert score.score == -1


# ═══ MetricEngineFacade ═══

class TestMetricEngineFacade:

    @pytest.mark.asyncio
    async def test_calculate_cross_domain_returns_metrics(self):
        facade = MetricEngineFacade()
        inputs = [_make_input(
            relevant_domains=["cardiology"],
            expected_conflicts=[{"s1": "a", "s2": "b"}],
            domain_results={
                "cardiology": {
                    "activated": True,
                    "contribution": 0.8,
                    "conflicts": [{"type": "test"}],
                },
            },
            execution_time_ms=500,
        )]
        result = await facade.calculate_cross_domain(inputs)
        assert result is not None

    @pytest.mark.asyncio
    async def test_calculate_cross_domain_all_na(self):
        facade = MetricEngineFacade()
        inputs = [_make_input()]
        result = await facade.calculate_cross_domain(inputs)
        assert result is None

    @pytest.mark.asyncio
    async def test_calculate_all(self):
        facade = MetricEngineFacade()
        inputs = [_make_input(
            relevant_domains=["cardiology"],
            domain_results={"cardiology": {"activated": True, "contribution": 0.8}},
            execution_time_ms=500,
        )]
        run_metrics = await facade.calculate_all(inputs)
        assert run_metrics.overall_score >= 0
        assert run_metrics.l1 is not None
        assert run_metrics.cross_domain is not None
