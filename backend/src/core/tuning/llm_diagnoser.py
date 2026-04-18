"""LLM 诊断器:Bad Case 语义深度分析"""

import json
from typing import Any, Dict, List, Optional

from json_repair import repair_json

from src.schemas import LLMDiagnosis, LLMFinding, TuningSuggestion
from src.utils.logger import logger

MIN_BAD_CASES_FOR_DIAGNOSIS = 3


class LLMDiagnoser:
    """LLM 诊断器:对失败测试用例进行语义分析"""

    def __init__(
        self,
        test_run_result_repo=None,
        test_case_repo=None,
        prompt_mgr=None,
        llm_factory=None,
    ):
        """初始化 LLM 诊断器"""
        self.test_run_result_repo = test_run_result_repo
        self.test_case_repo = test_case_repo
        self.prompt_mgr = prompt_mgr
        self.llm_factory = llm_factory

    async def diagnose(self, run_id: str) -> Optional[LLMDiagnosis]:
        """对指定测试运行的 Bad Case 进行诊断"""
        failed_results = await self.test_run_result_repo.get_failed_results(run_id)

        if len(failed_results) < MIN_BAD_CASES_FOR_DIAGNOSIS:
            logger.info(
                f"Bad Case 数量 {len(failed_results)} < {MIN_BAD_CASES_FOR_DIAGNOSIS},跳过 LLM 诊断"
            )
            return None

        bad_cases_data = await self._collect_bad_cases_data(failed_results)
        summary_stats = self._aggregate_bad_cases(bad_cases_data)

        if self.prompt_mgr:
            prompt_content = await self.prompt_mgr.get_prompt("rag_tuning_diagnosis")
        else:
            prompt_content = "你是一个 RAG 系统诊断专家。请分析以下失败的测试用例 (Bad Case),找出共性根因,并给出具体、可操作的优化建议。"

        llm_input = {
            "bad_cases": bad_cases_data,
            "summary_stats": summary_stats,
        }

        if self.llm_factory:
            llm = self.llm_factory.create(scene="report_generation")
            response = await llm.ainvoke(
                messages=[
                    {"role": "system", "content": prompt_content},
                    {
                        "role": "user",
                        "content": json.dumps(llm_input, ensure_ascii=False),
                    },
                ]
            )
            raw_output = (
                response.content if hasattr(response, "content") else str(response)
            )
        else:
            raw_output = '{"summary": "测试", "findings": [], "recommendations": []}'

        diagnosis = self._parse_llm_output(raw_output)

        if diagnosis:
            logger.info(
                f"LLM 诊断完成: {len(diagnosis.findings)} 个发现, {len(diagnosis.recommendations)} 条建议"
            )

        return diagnosis

    async def _collect_bad_cases_data(
        self, failed_results: List[Any]
    ) -> List[Dict[str, Any]]:
        """收集 Bad Case 详细数据"""
        bad_cases = []
        for result in failed_results:
            if self.test_case_repo:
                test_case = await self.test_case_repo.get_by_id(result.test_case_id)
            else:
                test_case = None

            if not test_case:
                bad_cases.append(
                    {
                        "query": getattr(result, "query", ""),
                        "domain": "unknown",
                        "age": 0,
                        "expected_keywords": [],
                        "actual_keywords": [],
                        "recall": getattr(result, "recall", 0.0) or 0.0,
                        "retrieved_docs_count": getattr(result, "actual_count", 0) or 0,
                        "avg_relevance": 0.0,
                    }
                )
                continue

            actual_keywords = self._extract_keywords_from_results(result)
            avg_relevance = self._compute_avg_relevance(result)

            bad_cases.append(
                {
                    "query": getattr(result, "query", ""),
                    "domain": test_case.domain.value
                    if hasattr(test_case.domain, "value")
                    else str(test_case.domain),
                    "age": float(test_case.age),
                    "expected_keywords": getattr(test_case, "expected_keywords", [])
                    or [],
                    "actual_keywords": actual_keywords,
                    "recall": getattr(result, "recall", 0.0) or 0.0,
                    "retrieved_docs_count": getattr(result, "actual_count", 0) or 0,
                    "avg_relevance": avg_relevance,
                }
            )

        return bad_cases

    def _extract_keywords_from_results(self, result: Any) -> List[str]:
        """从检索结果中提取实际出现的关键词"""
        if not hasattr(result, "retrieved_docs") or not result.retrieved_docs:
            return []

        all_text = "".join(
            doc.content for doc in result.retrieved_docs if hasattr(doc, "content")
        )

        try:
            import jieba

            words = jieba.lcut(all_text)
        except ImportError:
            words = all_text.split()

        from collections import Counter

        stopwords = {
            "的",
            "了",
            "是",
            "在",
            "和",
            "与",
            "或",
            "a",
            "the",
            "is",
            "in",
            " ",
            "\n",
        }
        keywords = [
            w.strip()
            for w in words
            if len(w.strip()) > 1 and w.strip() not in stopwords
        ]
        return [word for word, _ in Counter(keywords).most_common(20)]

    def _compute_avg_relevance(self, result: Any) -> float:
        """计算检索结果的平均相关度分数"""
        if not hasattr(result, "retrieved_docs") or not result.retrieved_docs:
            return 0.0

        scores = [
            doc.score
            for doc in result.retrieved_docs
            if hasattr(doc, "score") and doc.score is not None
        ]
        return sum(scores) / len(scores) if scores else 0.0

    def _aggregate_bad_cases(self, bad_cases: List[Dict[str, Any]]) -> Dict[str, Any]:
        """聚合 Bad Case 统计信息"""
        if not bad_cases:
            return {"total_bad_cases": 0}

        domain_distribution = {}
        for case in bad_cases:
            domain = case.get("domain", "unknown")
            domain_distribution[domain] = domain_distribution.get(domain, 0) + 1

        age_distribution = {}
        for case in bad_cases:
            age = case.get("age", 0)
            if age < 2:
                bucket = "0-2"
            elif age < 4:
                bucket = "2-4"
            elif age < 6:
                bucket = "4-6"
            else:
                bucket = "6+"
            age_distribution[bucket] = age_distribution.get(bucket, 0) + 1

        avg_relevance = sum(c.get("avg_relevance", 0) for c in bad_cases) / len(
            bad_cases
        )

        return {
            "total_bad_cases": len(bad_cases),
            "domain_distribution": domain_distribution,
            "age_distribution": age_distribution,
            "avg_relevance": round(avg_relevance, 4),
        }

    def _parse_llm_output(self, raw_output: str) -> Optional[LLMDiagnosis]:
        """解析 LLM 输出,使用 json-repair 修复格式问题"""
        try:
            repaired = repair_json(raw_output)
            parsed = json.loads(repaired)

            recommendations = []
            for idx, rec in enumerate(parsed.get("recommendations", [])):
                recommendations.append(
                    TuningSuggestion(
                        id=f"llm_diag_{idx}_{rec.get('param', '')}",
                        param_name=rec.get("param", ""),
                        current_value=None,
                        suggested_value=rec.get("suggested_value"),
                        action=rec.get("action", ""),
                        reason="",
                        expected_effect=rec.get("expected_effect", ""),
                        priority=rec.get("priority", "medium"),
                        source="llm",
                    )
                )

            findings = []
            for f in parsed.get("findings", []):
                findings.append(
                    LLMFinding(
                        category=f.get("category", ""),
                        description=f.get("description", ""),
                        confidence=f.get("confidence", 0.0),
                    )
                )

            return LLMDiagnosis(
                summary=parsed.get("summary", ""),
                findings=findings,
                recommendations=recommendations,
            )
        except Exception as e:
            logger.error(f"LLM 输出解析失败: {e}")
            return None
