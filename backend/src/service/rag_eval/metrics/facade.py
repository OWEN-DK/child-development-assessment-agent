"""MetricEngineFacade - 双轨评估统一门面

协调三层标准化指标计算和六层诊断引擎，提供并行双轨评估能力。
"""

import asyncio
from src.schemas.rag_eval.metrics import MetricInput, RunMetrics, MetricScore
from src.schemas.rag_eval.diagnosis import DiagnosisResult, LayerResult
from src.schemas.rag_eval.test_run import TestRunRead, TestRunResultItem
from src.service.rag_eval.metrics.scoring.facade import ScoringFacade
from src.service.rag_eval.metrics.diagnosis.orchestrator import (
    DiagnosisOrchestrator,
)


class MetricEngineFacade:
    """双轨评估统一门面

    三层指标提供标准化得分，用于横向比较和趋势追踪。
    六层诊断提供具体问题定位和修复建议，用于深度调试。
    两者并行计算，互不依赖。
    """

    def __init__(
        self,
        scoring_facade: ScoringFacade,
        diagnosis_orchestrator: DiagnosisOrchestrator,
    ):
        self._scoring = scoring_facade
        self._diagnosis = diagnosis_orchestrator

    async def calculate_all(self, results: list) -> RunMetrics:
        """计算三层标准化指标

        Args:
            results: MetricInput 或 TestRunResultItem 对象列表

        Returns:
            RunMetrics: 包含 L1/L2/L3 三层指标和加权综合得分的完整指标
        """
        metric_inputs = self._to_metric_inputs(results)
        return await self._scoring.calculate_all(metric_inputs)

    async def diagnose_all(
        self,
        run_id: str,
        results: list,
        run_data: TestRunRead = None,
    ) -> DiagnosisResult:
        """执行六层诊断

        按顺序执行 Layer 1→6，单层失败不阻塞后续层。
        各层独立返回 LayerResult，包含 issues 和 suggestions。

        Args:
            run_id: 测试运行 ID
            results: 测试用例执行结果列表
            run_data: 运行级别元数据（可选）

        Returns:
            DiagnosisResult: 六层诊断完整结果
        """
        return await self._diagnosis.run_all(run_id, results, run_data)

    async def calculate_and_diagnose(
        self,
        run_id: str,
        results: list,
        run_data: TestRunRead = None,
    ) -> tuple[RunMetrics, DiagnosisResult]:
        """并行执行双轨评估

        三层指标计算和六层诊断同时进行，最大化效率。

        Args:
            run_id: 测试运行 ID
            results: 测试用例执行结果列表
            run_data: 运行级别元数据（可选）

        Returns:
            (RunMetrics, DiagnosisResult) 元组
        """
        metrics, diagnosis = await asyncio.gather(
            self.calculate_all(results),
            self.diagnose_all(run_id, results, run_data),
        )
        return metrics, diagnosis

    async def calculate_layer(
        self,
        layer: int,
        results: list,
    ) -> dict[str, MetricScore]:
        """只计算指定层的三层指标

        Args:
            layer: 层级编号 (1/2/3)
            results: MetricInput 或 TestRunResultItem 对象列表

        Returns:
            指标名 → MetricScore 的映射字典
        """
        metric_inputs = self._to_metric_inputs(results)
        return await self._scoring.calculate_layer(layer, metric_inputs)

    @staticmethod
    def _to_metric_inputs(results: list) -> list[MetricInput]:
        """将 TestRunResultItem 列表转换为 MetricInput 列表（已是 MetricInput 则直接返回）"""
        if not results:
            return []
        if isinstance(results[0], MetricInput):
            return results
        return [
            MetricInput(
                run_id=r.run_id,
                test_case_id=r.test_case_id,
                query=r.query,
                retrieved_contexts=r.retrieved_contexts or r.retrieved_doc_ids or [],
                expected_knowledge_ids=r.expected_knowledge_ids or [],
                actual_knowledge_ids=r.actual_knowledge_ids or [],
                actual_answer=r.actual_answer,
                execution_time_ms=r.execution_time_ms,
            )
            for r in results
        ]

    async def diagnose_layer(
        self,
        layer: int,
        run_id: str,
        results: list,
        run_data: TestRunRead = None,
    ) -> LayerResult:
        """只执行指定层的六层诊断

        Args:
            layer: 诊断层编号 (1-6)
            run_id: 测试运行 ID
            results: 测试用例执行结果列表
            run_data: 运行级别元数据（可选）

        Returns:
            LayerResult: 该层的诊断结果
        """
        return await self._diagnosis.run_layer(layer, run_id, results, run_data)
