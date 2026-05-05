"""Layer 3: LLM 诊断

仅对失败用例（passed=False）使用 LLM 深度分析：
偏离分析、幻觉检测、相关性判断。
通过配置禁用时返回 skip。
"""

import json
import time
from typing import Optional

from src.core.config.cache import ConfigCache
from src.core.llm.factory import LLMServiceFactoryCompat
from src.core.prompt_impl.facade import PromptManager as PromptManagerImpl
from src.schemas.rag_eval.diagnosis import LayerIssue, LayerResult
from src.schemas.rag_eval.test_run import TestRunRead, TestRunResultItem
from src.service.rag_eval.metrics.diagnosis.diagnosis_utils import (
    calculate_layer_score, determine_layer_status)
from src.service.rag_eval.metrics.diagnosis.orchestrator import DiagnosisLayer
from src.utils.logger import logger

_PROMPT_DEV = "rag.eval.diagnosis.layer3.deviation_analysis"
_PROMPT_HAL = "rag.eval.diagnosis.layer3.hallucination_detection"
_MAX_CASES = 10


class Layer3LLM(DiagnosisLayer):
    """LLM 深度诊断层——仅对失败用例执行偏离分析和幻觉检测"""

    def __init__(self, prompt_manager: Optional[PromptManagerImpl] = None,
                 config_cache: Optional[ConfigCache] = None):
        self._pm = prompt_manager or PromptManagerImpl()
        self._config_cache = config_cache or ConfigCache.get_instance()

    @property
    def layer_number(self) -> int: return 3
    @property
    def name(self) -> str: return "LLM 诊断"

    async def diagnose(
        self, run_id: str, results: list[TestRunResultItem], run_data: TestRunRead
    ) -> LayerResult:
        start = time.time()

        enabled = self._get_config(self._config_cache, "rag.eval.diagnosis.layer3.enabled", True)
        if not enabled:
            return LayerResult(
                layer=self.layer_number, name=self.name, status="skip", score=1.0,
                issues=[LayerIssue(severity="info", category="disabled",
                         description="LLM 诊断已通过配置禁用", affected_items=[run_id])],
                details={"reason": "config_disabled"},
                execution_time_ms=int((time.time() - start) * 1000))

        failed = [r for r in results if not r.passed]
        if not failed:
            return LayerResult(layer=self.layer_number, name=self.name, status="pass", score=1.0,
                               issues=[], details={"failed_count": 0},
                               execution_time_ms=int((time.time() - start) * 1000))

        issues: list[LayerIssue] = []
        for case in failed[:_MAX_CASES]:
            cid = case.test_case_id or case.id
            try:
                issues.extend(await self._analyze_deviation(case, cid))
                issues.extend(await self._detect_hallucination(case, cid))
            except Exception as e:
                logger.error(f"Layer3 LLM 诊断用例 {cid} 失败: {e}")
                issues.append(LayerIssue(severity="warning", category="llm_error",
                              description=f"用例 {cid}: LLM 调用失败", affected_items=[cid]))

        return LayerResult(
            layer=self.layer_number, name=self.name,
            status=determine_layer_status(issues),
            score=calculate_layer_score(issues), issues=issues,
            details={"total_failed": len(failed), "analyzed": min(len(failed), _MAX_CASES),
                     "prompts_used": [_PROMPT_DEV, _PROMPT_HAL]},
            execution_time_ms=int((time.time() - start) * 1000))

    async def _analyze_deviation(self, case: TestRunResultItem, cid: str) -> list[LayerIssue]:
        from src.schemas.llm import LLMMessage, LLMRequest
        try:
            prompt = await self._pm.get_prompt(_PROMPT_DEV, variables={
                "query": case.query, "actual_answer": case.actual_answer or "",
                "expected_knowledge_ids": json.dumps(case.expected_knowledge_ids or [])})
            llm = LLMServiceFactoryCompat.create()
            resp = await llm.chat(LLMRequest(
                messages=[LLMMessage(role="user", content=prompt)],
                model_name=llm.get_model_name(),
            ))
            analysis = _parse_json(resp.content, cid)
            if analysis.get("has_deviation"):
                return [LayerIssue(
                    severity=analysis.get("severity", "warning"), category="answer_deviation",
                    description=f"用例 {cid}: {analysis.get('description', '回答偏离期望')}",
                    affected_items=[cid], suggestion=analysis.get("suggestion"))]
        except Exception as e:
            logger.error(f"偏离分析异常 {cid}: {e}")
        return []

    async def _detect_hallucination(self, case: TestRunResultItem, cid: str) -> list[LayerIssue]:
        from src.schemas.llm import LLMMessage, LLMRequest
        try:
            prompt = await self._pm.get_prompt(_PROMPT_HAL, variables={
                "query": case.query, "actual_answer": case.actual_answer or ""})
            llm = LLMServiceFactoryCompat.create()
            resp = await llm.chat(LLMRequest(
                messages=[LLMMessage(role="user", content=prompt)],
                model_name=llm.get_model_name(),
            ))
            analysis = _parse_json(resp.content, cid)
            if analysis.get("has_hallucination"):
                return [LayerIssue(
                    severity=analysis.get("severity", "critical"), category="hallucination",
                    description=f"用例 {cid}: {analysis.get('description', '检测到幻觉内容')}",
                    affected_items=[cid],
                    suggestion=analysis.get("suggestion", "审查 RAG 上下文准确性"))]
        except Exception as e:
            logger.error(f"幻觉检测异常 {cid}: {e}")
        return []


def _parse_json(response: str, cid: str) -> dict:
    if not response:
        return {}
    try:
        return json.loads(response)
    except json.JSONDecodeError:
        try:
            from json_repair import repair_json as _repair
            return json.loads(_repair(response))
        except Exception:
            logger.warning(f"LLM JSON 解析失败 {cid}: {response[:200]}")
            return {}
