"""Layer 1: 规则引擎

检查测试结果格式合规性：查询/答案非空、期望知识点完整、指标范围 [0,1]、
无 error_message、execution_time 合法（8 条规则）。
"""

import time
from typing import Optional

from src.core.config.cache import ConfigCache
from src.schemas.rag_eval.diagnosis import LayerIssue, LayerResult
from src.schemas.rag_eval.test_run import TestRunRead, TestRunResultItem
from src.service.rag_eval.metrics.diagnosis.diagnosis_utils import (
    calculate_layer_score, determine_layer_status, count_by_severity)
from src.service.rag_eval.metrics.diagnosis.orchestrator import DiagnosisLayer


class Layer1Rules(DiagnosisLayer):
    """规则引擎诊断层——检查测试结果格式合规性"""

    def __init__(self, config_cache: Optional[ConfigCache] = None):
        self._config_cache = config_cache or ConfigCache.get_instance()

    @property
    def layer_number(self) -> int: return 1
    @property
    def name(self) -> str: return "规则引擎"

    async def diagnose(
        self, run_id: str, results: list[TestRunResultItem], run_data: TestRunRead
    ) -> LayerResult:
        start = time.time()
        issues: list[LayerIssue] = []
        for item in results:
            issues.extend(self._check(item))

        crit, warn, _ = count_by_severity(issues)
        return LayerResult(
            layer=self.layer_number, name=self.name,
            status=determine_layer_status(issues),
            score=calculate_layer_score(issues),
            issues=issues,
            details={"total_items": len(results), "checked_rules": 8,
                     "critical_count": crit, "warning_count": warn},
            execution_time_ms=int((time.time() - start) * 1000),
        )

    def _check(self, item: TestRunResultItem) -> list[LayerIssue]:
        issues: list[LayerIssue] = []
        iid = item.test_case_id or item.id

        # 规则 1: 查询非空
        if not item.query or not item.query.strip():
            issues.append(LayerIssue(
                severity="critical", category="format_compliance",
                description=f"用例 {iid}: 查询为空或空白", affected_items=[iid],
                suggestion="填写有效查询文本"))

        # 规则 2: 答案非空（仅检查有答案字段的用例）
        if item.actual_answer is not None and not item.actual_answer.strip():
            issues.append(LayerIssue(
                severity="warning", category="format_compliance",
                description=f"用例 {iid}: 答案为空白", affected_items=[iid],
                suggestion="检查 RAG 生成流程，确保答案非空"))

        # 规则 5: expected_knowledge_ids 非空
        if not item.expected_knowledge_ids:
            issues.append(LayerIssue(
                severity="critical", category="required_field_missing",
                description=f"用例 {iid}: expected_knowledge_ids 为空", affected_items=[iid],
                suggestion="为测试用例配置期望知识片段 ID 列表"))

        # 规则 6: 检索指标在 [0, 1]
        for fn, val in [("precision", item.precision), ("recall", item.recall),
                        ("f1", item.f1), ("mrr", item.mrr), ("ndcg", item.ndcg)]:
            if val is not None and (val < 0.0 or val > 1.0):
                issues.append(LayerIssue(
                    severity="warning", category="invalid_metric_range",
                    description=f"用例 {iid}: {fn}={val} 超出 [0,1] 范围", affected_items=[iid],
                    suggestion="检查指标计算逻辑或数据源"))

        # 规则 7: 无 error_message
        if item.error_message:
            issues.append(LayerIssue(
                severity="critical", category="execution_error",
                description=f"用例 {iid}: 执行异常 - {item.error_message}", affected_items=[iid],
                suggestion="查看检索或生成流程的错误日志"))

        # 规则 8: execution_time_ms > 0 且 < 超时阈值
        if item.execution_time_ms is not None:
            timeout = self._get_config(self._config_cache, "rag.eval.diagnosis.timeout_ms", 60000)
            if item.execution_time_ms <= 0:
                issues.append(LayerIssue(
                    severity="warning", category="invalid_metric_range",
                    description=f"用例 {iid}: execution_time_ms={item.execution_time_ms} ≤ 0",
                    affected_items=[iid]))
            elif item.execution_time_ms > timeout:
                issues.append(LayerIssue(
                    severity="warning", category="timeout",
                    description=f"用例 {iid}: 耗时 {item.execution_time_ms}ms，超阈值 {timeout}ms",
                    affected_items=[iid], suggestion="优化检索或生成性能"))

        return issues
