"""Layer 5: 效果评估

评估 RAG 系统综合效果：Embedding 质量（查询-答案相似度）、错误模式聚类分析。
"""

import time
from typing import Optional

from src.core.config.cache import ConfigCache
from src.schemas.rag_eval.diagnosis import LayerIssue, LayerResult
from src.schemas.rag_eval.test_run import TestRunRead, TestRunResultItem
from src.service.rag_eval.metrics.diagnosis.diagnosis_utils import (
    calculate_layer_score, determine_layer_status)
from src.service.rag_eval.metrics.diagnosis.orchestrator import DiagnosisLayer
from src.utils.embedding_helper import EmbeddingHelper
from src.utils.logger import logger

_MIN_PATTERN = 2


class Layer5Effect(DiagnosisLayer):
    """效果评估诊断层——Embedding 相似度分析和错误模式聚类"""

    def __init__(self, embedding_helper: Optional[EmbeddingHelper] = None,
                 config_cache: Optional[ConfigCache] = None):
        self._eh = embedding_helper or EmbeddingHelper()
        self._config_cache = config_cache or ConfigCache.get_instance()

    @property
    def layer_number(self) -> int: return 5
    @property
    def name(self) -> str: return "效果评估"

    async def diagnose(
        self, run_id: str, results: list[TestRunResultItem], run_data: TestRunRead
    ) -> LayerResult:
        start = time.time()
        issues: list[LayerIssue] = []

        issues.extend(await self._check_embedding(results))
        issues.extend(self._check_patterns(results))

        return LayerResult(
            layer=self.layer_number, name=self.name,
            status=determine_layer_status(issues),
            score=calculate_layer_score(issues), issues=issues,
            details={"total_results": len(results),
                     "failed_count": sum(1 for r in results if not r.passed)},
            execution_time_ms=int((time.time() - start) * 1000))

    async def _check_embedding(self, results: list[TestRunResultItem]) -> list[LayerIssue]:
        """检查查询-答案 embedding 相似度（抽样）"""
        low: list[str] = []
        for r in results[::5]:  # 抽样减少计算量
            if not r.query or not r.actual_answer:
                continue
            try:
                qe = await self._eh.embed_text(r.query)
                ae = await self._eh.embed_text(r.actual_answer)
                if not qe or not ae:
                    continue
                from src.utils.similarity import cosine_similarity
                if cosine_similarity(qe, ae) < 0.3:
                    low.append(r.test_case_id or r.id)
            except Exception as e:
                logger.debug(f"Embedding 相似度计算失败: {e}")
                continue
        if low:
            return [LayerIssue(
                severity="warning", category="embedding_quality",
                description=f"{len(low)} 个用例查询-答案语义相似度 < 0.3",
                affected_items=low, suggestion="检查 embedding 模型领域匹配或审查答案质量")]
        return []

    def _check_patterns(self, results: list[TestRunResultItem]) -> list[LayerIssue]:
        """检查失败用例共性模式"""
        issues: list[LayerIssue] = []
        failed = [r for r in results if not r.passed]
        if len(failed) < _MIN_PATTERN:
            return issues

        # 模式: 全零指标（检索完全失败）
        zero = [r.test_case_id or r.id for r in failed
                if (r.precision is None or r.precision == 0.0)
                and (r.recall is None or r.recall == 0.0)]
        if len(zero) >= _MIN_PATTERN:
            r = len(zero) / len(failed)
            issues.append(LayerIssue(
                severity="critical" if r > 0.5 else "warning", category="error_pattern",
                description=f"{len(zero)}/{len(failed)} 失败用例 precision 和 recall 均为零",
                affected_items=zero, suggestion="检查索引是否损坏或检索参数配置"))

        # 模式: 接近超时
        timeout_ms = self._get_config(self._config_cache, "rag.eval.diagnosis.timeout_ms", 60000)
        to_cases = [r.test_case_id or r.id for r in failed
                    if r.execution_time_ms is not None and r.execution_time_ms > timeout_ms * 0.8]
        if len(to_cases) >= _MIN_PATTERN:
            issues.append(LayerIssue(
                severity="warning", category="error_pattern",
                description=f"{len(to_cases)} 个失败用例接近或超时",
                affected_items=to_cases, suggestion="优化性能或增加超时阈值"))

        return issues
