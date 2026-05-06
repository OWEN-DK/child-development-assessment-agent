"""Layer 4: 数据质量

检查底层数据质量：Golden 覆盖度、分块质量、文档时效性。
"""

import time
from datetime import datetime
from typing import Optional

from src.core.config.cache import ConfigCache
from src.core.database import async_session_factory
from src.repository.document_repository import SourceDocumentRepository
from src.schemas.rag_eval.diagnosis import LayerIssue, LayerResult
from src.schemas.rag_eval.test_run import TestRunRead, TestRunResultItem
from src.service.rag_eval.metrics.diagnosis.diagnosis_utils import (
    calculate_layer_score, count_affected_cases, determine_layer_status)
from src.service.rag_eval.metrics.diagnosis.orchestrator import DiagnosisLayer
from src.utils.logger import logger

_STALENESS_DAYS = 90
_MIN_CHUNKS = 3


class Layer4DataQuality(DiagnosisLayer):
    """数据质量诊断层——检查 Golden 覆盖度、分块完整性、文档时效性"""

    def __init__(self, source_document_repository: Optional[SourceDocumentRepository] = None,
                 config_cache: Optional[ConfigCache] = None):
        self._sdr = source_document_repository or SourceDocumentRepository(async_session_factory)
        self._config_cache = config_cache or ConfigCache.get_instance()

    @property
    def layer_number(self) -> int: return 4
    @property
    def name(self) -> str: return "数据质量"

    async def diagnose(
        self, run_id: str, results: list[TestRunResultItem], run_data: TestRunRead
    ) -> LayerResult:
        start = time.time()
        issues: list[LayerIssue] = []

        # 收集文档 ID
        doc_ids: set[str] = set()
        for r in results:
            for did in (r.retrieved_doc_ids or []):
                doc_ids.add(did)
            for did in (r.relevant_doc_ids or []):
                doc_ids.add(did)

        # Golden 覆盖度
        golden = self._get_config(self._config_cache, "rag.eval.diagnosis.layer4.golden_case_ids", [])
        if golden:
            issues.extend(self._check_golden(golden, results))

        # 分块质量
        issues.extend(self._check_chunks(results))

        # 文档时效性
        if doc_ids:
            issues.extend(await self._check_stale(doc_ids))

        total = len(results)
        return LayerResult(
            layer=self.layer_number, name=self.name,
            status=determine_layer_status(issues),
            score=calculate_layer_score(issues, total),
            total_cases=total,
            affected_cases=count_affected_cases(issues),
            issues=issues,
            details={"documents_involved": len(doc_ids), "golden_case_ids": golden},
            execution_time_ms=int((time.time() - start) * 1000))

    def _check_golden(self, golden: list[str], results: list[TestRunResultItem]) -> list[LayerIssue]:
        issues: list[LayerIssue] = []
        rids = {r.test_case_id for r in results}
        uncovered = set(golden) - rids
        ratio = len(rids & set(golden)) / len(golden) if golden else 1.0
        if ratio < 0.8:
            issues.append(LayerIssue(
                severity="critical" if ratio < 0.5 else "warning",
                category="golden_coverage",
                description=f"Golden 覆盖率仅 {ratio:.0%}", affected_items=list(uncovered),
                suggestion="将缺失 Golden 用例加入测试集"))
        return issues

    def _check_chunks(self, results: list[TestRunResultItem]) -> list[LayerIssue]:
        low = [r.test_case_id or r.id for r in results
               if len(r.retrieved_doc_ids or []) < _MIN_CHUNKS and r.query]
        if low:
            return [LayerIssue(
                severity="warning", category="chunk_quality",
                description=f"{len(low)} 个用例检索分块数 < {_MIN_CHUNKS}",
                affected_items=low, suggestion="检查索引完整性或增加检索 top_k")]
        return []

    async def _check_stale(self, doc_ids: set[str]) -> list[LayerIssue]:
        stale: list[str] = []
        for did in list(doc_ids)[:50]:
            try:
                doc = await self._sdr.get_by_id(did)
            except Exception:
                continue
            if doc is None:
                continue
            updated = getattr(doc, "updated_at", None) or getattr(doc, "created_at", None)
            if updated and (datetime.now() - updated.replace(tzinfo=None)).days > _STALENESS_DAYS:
                stale.append(did)
        if stale:
            return [LayerIssue(severity="info", category="document_staleness",
                     description=f"{len(stale)} 个文档超 {_STALENESS_DAYS} 天未更新",
                     affected_items=stale, suggestion="更新或重新索引过期文档")]
        return []
