"""跨域指标计算器

评估多域聚合管道的跨域融合效果。
4 项指标：域激活准确率、跨域覆盖率、冲突检测率、端到端延迟 P95。
每项指标可独立返回 N/A（当 Ground Truth 不可用时）。
"""
from typing import Any, Optional

from src.schemas.rag_eval.metrics import (
    CrossDomainMetrics,
    DomainContribution,
    MetricScore,
)


class IMetricCalculator:
    """指标计算器接口"""

    def calculate(self, inputs: list[dict[str, Any]]) -> MetricScore:
        raise NotImplementedError


class CrossDomainCalc(IMetricCalculator):
    """跨域指标计算器基类

    所有跨域指标共享输入结构：
    - test_case: 含 relevant_domains、expected_conflicts
    - result: 含 domain_results_json、passed、error_message
    - execution_results: 全部用例执行结果的列表
    """

    def calculate(self, inputs: list[dict[str, Any]]) -> MetricScore:
        raise NotImplementedError

    def _get_domain_results(self, result: dict[str, Any]) -> dict[str, Any]:
        return result.get("domain_results_json") or {}

    def _get_relevant_domains(self, test_case: dict[str, Any]) -> list[str]:
        return test_case.get("relevant_domains") or []

    def _get_expected_conflicts(self, test_case: dict[str, Any]) -> list[dict[str, Any]]:
        return test_case.get("expected_conflicts") or []


class DomainActivationAccCalc(CrossDomainCalc):
    """域激活准确率

    GT: TestCase.relevant_domains（期望激活的域）
    实际: PipelineCompiler 返回的 domain_results 中 activated=True 的域
    公式: |准确激活域 ∩ 期望激活域| / |期望激活域|
    空 relevant_domains → 返回 N/A (score=-1, passed=None)
    """

    def calculate(self, inputs: list[dict[str, Any]]) -> MetricScore:
        total_expected = 0
        total_correct = 0
        has_data = False

        for item in inputs:
            test_case = item.get("test_case", {})
            result = item.get("result", {})

            relevant = self._get_relevant_domains(test_case)
            if not relevant:
                continue

            has_data = True
            total_expected += len(relevant)

            domain_results = self._get_domain_results(result)
            for domain_id in relevant:
                info = domain_results.get(domain_id, {})
                if info.get("activated", False):
                    total_correct += 1

        if not has_data:
            return MetricScore(
                name="domain_activation_acc",
                display_name="域激活准确率",
                score=-1,  # N/A
                passed=None,  # 无法判断
                weight=0.25,
            )

        score = total_correct / total_expected if total_expected > 0 else 0.0
        return MetricScore(
            name="domain_activation_acc",
            display_name="域激活准确率",
            score=round(score, 4),
            passed=score >= 0.7,  # 默认阈值 0.7
            weight=0.25,
        )


class CrossDomainCoverageCalc(CrossDomainCalc):
    """跨域覆盖率

    公式: |有结果贡献的域 ∩ 期望激活域| / |期望激活域|
    有结果贡献 = domain_results[domain].contribution > 0
    """

    def calculate(self, inputs: list[dict[str, Any]]) -> MetricScore:
        total_expected = 0
        total_covered = 0
        has_data = False

        for item in inputs:
            test_case = item.get("test_case", {})
            result = item.get("result", {})

            relevant = self._get_relevant_domains(test_case)
            if not relevant:
                continue

            has_data = True
            total_expected += len(relevant)

            domain_results = self._get_domain_results(result)
            for domain_id in relevant:
                info = domain_results.get(domain_id, {})
                if info.get("contribution", 0) > 0:
                    total_covered += 1

        if not has_data:
            return MetricScore(
                name="cross_domain_coverage",
                display_name="跨域覆盖率",
                score=-1,
                passed=None,
                weight=0.25,
            )

        score = total_covered / total_expected if total_expected > 0 else 0.0
        return MetricScore(
            name="cross_domain_coverage",
            display_name="跨域覆盖率",
            score=round(score, 4),
            passed=score >= 0.7,
            weight=0.25,
        )


class ConflictDetectionRateCalc(CrossDomainCalc):
    """冲突检测率

    GT: TestCase.expected_conflicts（人工标注的已知跨域矛盾）
    实际: 管道 ConflictDetectExecutor 检测到的冲突数
    公式: 检测到的冲突数 / 期望冲突数
    空 expected_conflicts → 返回 N/A
    """

    def calculate(self, inputs: list[dict[str, Any]]) -> MetricScore:
        total_expected = 0
        total_detected = 0
        has_data = False

        for item in inputs:
            test_case = item.get("test_case", {})
            result = item.get("result", {})

            expected = self._get_expected_conflicts(test_case)
            if not expected:
                continue

            has_data = True
            total_expected += len(expected)

            # 从管道结果中提取检测到的冲突数
            # 冲突检测节点输出格式: {"conflicts": [...]}
            domain_results = self._get_domain_results(result)
            detected_count = 0
            for domain_info in domain_results.values():
                conflicts = domain_info.get("conflicts", [])
                if isinstance(conflicts, list):
                    detected_count += len(conflicts)

            total_detected += min(detected_count, len(expected))  # 上限为期望数

        if not has_data:
            return MetricScore(
                name="conflict_detection_rate",
                display_name="冲突检测率",
                score=-1,
                passed=None,
                weight=0.25,
            )

        score = total_detected / total_expected if total_expected > 0 else 0.0
        return MetricScore(
            name="conflict_detection_rate",
            display_name="冲突检测率",
            score=round(score, 4),
            passed=score >= 0.5,  # 冲突检测阈值 0.5
            weight=0.25,
        )


class E2ELatencyCalc(CrossDomainCalc):
    """端到端延迟 P95

    从所有 execution_time_ms 计算 P50/P95/P99/avg。
    不设硬阈值（threshold=0, always passed）。
    """

    def calculate(self, inputs: list[dict[str, Any]]) -> MetricScore:
        times = []
        for item in inputs:
            result = item.get("result", {})
            et = result.get("execution_time_ms")
            if et is not None:
                times.append(et)

        if not times:
            return MetricScore(
                name="e2e_latency_p95",
                display_name="端到端延迟 P95",
                score=-1,
                passed=None,
                weight=0.25,
            )

        sorted_times = sorted(times)
        n = len(sorted_times)

        def _percentile(p: float) -> int:
            idx = int(n * p / 100)
            return sorted_times[min(idx, n - 1)]

        p95 = _percentile(95)

        # 延迟分数：P95 < 1000ms → 1.0, P95 < 5000ms → 0.5, P95 > 10000ms → 0.0
        if p95 < 1000:
            score = 1.0
        elif p95 < 5000:
            score = 0.5 + 0.5 * (5000 - p95) / 4000
        else:
            score = max(0.0, 0.5 * (10000 - p95) / 5000)

        return MetricScore(
            name="e2e_latency_p95",
            display_name="端到端延迟 P95",
            score=round(score, 4),
            passed=True,  # 不设硬阈值
            weight=0.25,
        )
