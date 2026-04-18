"""Layer 3: LLM 诊断 - 分析 Bad Case 并提供失败类型分类、根因分析和建议"""

import asyncio
import json
import logging
from collections import defaultdict
from typing import Any

from json_repair import repair_json

logger = logging.getLogger(__name__)

FAILURE_TYPES = [
    "未召回",
    "排序倒置",
    "误杀",
    "语义不匹配",
    "部分召回",
    "年龄过滤排除",
    "重排序误判",
]

ROOT_CAUSES = [
    "Embedding 质量问题",
    "分块不合理",
    "关键词缺失",
    "同义词未覆盖",
    "年龄过滤过严",
    "重排序模型不匹配",
    "查询路由错误",
    "分块粒度不当",
]

LLM_DIAGNOSIS_PROMPT = """
你是一位 RAG 检索系统诊断专家。请分析以下 Bad Case，给出失败类型、根因和建议措施。

当前配置摘要：
{config_summary}

Bad Case 列表（共 {count} 条）：
{bad_cases}

请以 JSON 数组格式返回，每条包含：
- query: 查询文本
- failure_type: 失败类型（{failure_types}）
- root_cause: 根因（{root_causes}）
- confidence: 置信度 (0-1)
- suggestion: 建议措施
- priority: 优先级 (HIGH/MEDIUM/LOW)

只输出 JSON，不要其他内容。
"""


class Layer3LLMDiagnosis:
    """Layer 3: LLM 诊断"""

    def __init__(self, session_factory, test_run):
        self.session_factory = session_factory
        self.test_run = test_run

    async def execute(self) -> dict:
        """执行 LLM 诊断"""
        bad_cases = await self._get_bad_cases()

        if len(bad_cases) < 5:
            return {"status": "skipped", "data": {"reason": "Bad Case 数量不足 5 条"}}

        # 抽样策略
        if len(bad_cases) > 50:
            bad_cases = self._stratified_sample(bad_cases, 50)

        config_snapshot = getattr(self.test_run, "config_snapshot", None) or {}
        config_summary = json.dumps(config_snapshot, ensure_ascii=False)[:500]
        bad_cases_text = json.dumps(bad_cases, ensure_ascii=False)

        prompt = LLM_DIAGNOSIS_PROMPT.format(
            config_summary=config_summary,
            count=len(bad_cases),
            bad_cases=bad_cases_text,
            failure_types="/".join(FAILURE_TYPES),
            root_causes="/".join(ROOT_CAUSES),
        )

        try:
            response = await self._call_llm_with_retry(prompt, max_retries=2)
            diagnosis = self._parse_llm_response(response)
            return self._summarize(diagnosis)
        except Exception as e:
            logger.error(f"Layer 3 LLM 诊断失败: {e}")
            return {
                "status": "degraded",
                "data": {"reason": "LLM 服务不可用，已跳过深度诊断"},
            }

    async def _get_bad_cases(self) -> list:
        """获取 Bad Case 列表 (hit_at_5 = 0)"""
        from sqlalchemy import select

        from src.models.rag_eval.test_case import RagEvalTestCase
        from src.models.rag_eval.test_run_result import RagEvalTestRunResult

        async with self.session_factory() as session:
            results = await session.execute(
                select(RagEvalTestRunResult)
                .where(RagEvalTestRunResult.run_id == self.test_run.id)
                .where(RagEvalTestRunResult.hit_at_5 == 0)
            )
            run_results = results.scalars().all()

            bad_cases = []
            for rr in run_results:
                tc_result = await session.execute(
                    select(RagEvalTestCase).where(RagEvalTestCase.id == rr.case_id)
                )
                tc = tc_result.scalar_one_or_none()

                bad_cases.append(
                    {
                        "query": rr.query or "",
                        "expected_docs": tc.expected_document_ids if tc else [],
                        "actual_docs": rr.matched_doc_ids or [],
                        "matched_scores": rr.matched_doc_scores or [],
                        "hit_at_1": rr.hit_at_1,
                        "hit_at_3": rr.hit_at_3,
                        "hit_at_5": rr.hit_at_5,
                        "domain": tc.domain.value if tc and tc.domain else "unknown",
                        "age_months": tc.age_months if tc else 0,
                    }
                )

            return bad_cases

    def _stratified_sample(self, bad_cases: list, target: int) -> list:
        """按 domain × age_group 分层抽样"""
        by_stratum = defaultdict(list)
        for bc in bad_cases:
            domain = bc.get("domain", "unknown")
            age_group = bc.get("age_group", "unknown")
            by_stratum[(domain, age_group)].append(bc)

        sampled = []
        per_stratum = max(3, target // len(by_stratum))
        for cases in by_stratum.values():
            sampled.extend(cases[:per_stratum])

        return sampled[:target]

    async def _call_llm_with_retry(self, prompt: str, max_retries: int = 2) -> str:
        """带重试的 LLM 调用"""
        from src.core.llm.factory import LLMFramework, LLMServiceFactory
        from src.schemas import LLMMessage, LLMRequest

        factory = self._get_llm_factory()
        llm = await factory.create("validation", LLMFramework.LANGCHAIN)
        last_error = None

        for attempt in range(max_retries):
            try:
                request = LLMRequest(
                    messages=[LLMMessage(role="user", content=prompt)],
                    model_name="",
                    temperature=0.3,
                    max_tokens=4096,
                    scenario="validation_diagnosis",
                )
                response = await asyncio.wait_for(llm.chat(request), timeout=120)
                return response.content
            except asyncio.TimeoutError:
                last_error = "超时"
                if attempt < max_retries - 1:
                    await asyncio.sleep(2)
            except Exception as e:
                if "429" in str(e) or "rate limit" in str(e).lower():
                    last_error = "Rate Limit"
                    await asyncio.sleep(5)
                else:
                    raise

        raise Exception(f"LLM 调用失败 ({last_error})")

    def _get_llm_factory(self):
        """获取 LLM 工厂实例（延迟初始化）"""
        from src.config.core.manager import config_manager
        from src.core.llm.provider_registry import ProviderRegistry

        provider_registry = ProviderRegistry()
        return LLMServiceFactory(config_manager, provider_registry)

    def _parse_llm_response(self, response: str) -> list:
        """解析 LLM 响应，使用 json-repair 修复"""
        try:
            repaired = repair_json(response)
            return json.loads(repaired) if isinstance(repaired, str) else repaired
        except Exception:
            return []

    def _summarize(self, diagnosis: list) -> dict:
        """汇总统计"""
        failure_type_counts = {}
        root_cause_counts = {}

        for d in diagnosis:
            ft = d.get("failure_type", "unknown")
            rc = d.get("root_cause", "unknown")
            failure_type_counts[ft] = failure_type_counts.get(ft, 0) + 1
            root_cause_counts[rc] = root_cause_counts.get(rc, 0) + 1

        return {
            "status": "completed",
            "data": {
                "diagnosis": diagnosis,
                "summary": {
                    "most_common_failure_type": max(
                        failure_type_counts, key=failure_type_counts.get
                    )
                    if failure_type_counts
                    else None,
                    "most_common_root_cause": max(
                        root_cause_counts, key=root_cause_counts.get
                    )
                    if root_cause_counts
                    else None,
                    "total_analyzed": len(diagnosis),
                },
            },
        }
