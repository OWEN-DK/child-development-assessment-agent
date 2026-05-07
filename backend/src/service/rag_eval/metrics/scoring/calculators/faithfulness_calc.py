"""L2 忠实度计算器——FaithfulnessCalculator（灵感来自 RAGAS）

优化：合并声明提取与验证为单次 LLM 调用，从 1+N 次降至 1 次。
"""

import json
from typing import Optional

from src.core.llm.factory import LLMServiceFactory
from src.core.prompt_impl.facade import PromptManager
from src.schemas.llm import LLMMessage, LLMRequest
from src.schemas.rag_eval.metrics import MetricInput, MetricOutput
from src.service.rag_eval.metrics.scoring.base import MetricCalculator
from src.utils.logger import logger


class FaithfulnessCalculator(MetricCalculator):
    """忠实度（灵感来自 RAGAS）

    计算: 被上下文支持的声明数 / 总声明数
    阈值: ≥ 0.8

    流程（单次 LLM 调用）：
    1. 使用批量 prompt 同时提取声明并验证每个声明是否被上下文支持
    2. 解析 JSON 结果，计算 supported / total
    """

    def __init__(
        self,
        llm_factory: Optional[LLMServiceFactory] = None,
        prompt_manager: Optional[PromptManager] = None,
        config_cache=None,
    ):
        super().__init__(config_cache)
        self._llm_factory = llm_factory
        self._prompt_manager = prompt_manager or PromptManager()

    @property
    def name(self) -> str:
        return "faithfulness"

    @property
    def layer(self) -> int:
        return 2

    @property
    def description(self) -> str:
        return "忠实度：答案中声明被上下文支持的比例"

    async def calculate(self, input_data: MetricInput) -> MetricOutput:
        threshold = await self._get_threshold()

        if not input_data.actual_answer or not input_data.actual_answer.strip():
            return MetricOutput(score=0.0, passed=False, threshold=threshold, details={"reason": "答案为空"})

        if not input_data.retrieved_contexts:
            return MetricOutput(score=0.0, passed=False, threshold=threshold, details={"reason": "无检索上下文"})

        contexts_text = "\n---\n".join(input_data.retrieved_contexts)

        # 单次 LLM 调用：提取声明 + 验证
        claims_data = await self._batch_extract_and_verify(input_data.actual_answer, contexts_text)

        if not claims_data:
            return MetricOutput(score=0.0, passed=False, threshold=threshold,
                                details={"reason": "未能提取声明", "claims": []})

        supported = sum(1 for c in claims_data if c.get("supported", False))
        total = len(claims_data)
        score = supported / total if total > 0 else 0.0

        return MetricOutput(
            score=round(score, 4),
            passed=score >= threshold,
            threshold=threshold,
            details={"total_claims": total, "supported_claims": supported, "claim_results": claims_data},
        )

    async def _batch_extract_and_verify(self, answer: str, contexts: str) -> list[dict]:
        """单次 LLM 调用：提取声明并验证是否被上下文支持（解析失败自动重试 1 次）"""
        if not self._llm_factory:
            return self._fallback(answer)

        prompt = await self._prompt_manager.get_prompt(
            "rag.eval.metric.faithfulness_batch_verify",
            variables={"answer": answer, "contexts": contexts},
        )

        for attempt in range(2):
            try:
                llm = await self._llm_factory.create("rag_eval", "langchain")
                response = await llm.chat(LLMRequest(
                    messages=[LLMMessage(role="user", content=prompt)],
                    timeout=120,
                ))
                result = self._parse_batch_result(response.content)
                if result:
                    return result
                logger.warning(f"忠实度批量解析为空（第 {attempt + 1} 次），重试")
            except Exception as e:
                logger.warning(f"忠实度批量调用失败（第 {attempt + 1} 次）: {e}")

        logger.warning("忠实度批量调用 2 次均失败，降级为逐条模式")
        return await self._fallback_sequential(answer, contexts)

    def _parse_batch_result(self, text: str) -> list[dict]:
        """解析 LLM 返回的批量验证结果 JSON（支持截断恢复）"""
        import re
        # 清理 markdown 代码块包裹
        cleaned = re.sub(r'```(?:json)?\s*', '', text).strip().rstrip('`').strip()

        def _extract_claims(data) -> list[dict]:
            """从数据中提取声明列表"""
            items = data["claims"] if isinstance(data, dict) and "claims" in data else data if isinstance(data, list) else []
            return [{"claim": str(c.get("claim", "")), "supported": bool(c.get("supported", False))}
                    for c in items if isinstance(c, dict)]

        # 策略1：直接解析
        try:
            result = json.loads(cleaned)
            claims = _extract_claims(result)
            if claims:
                return claims
        except json.JSONDecodeError:
            pass

        # 策略2：提取 JSON 子串
        try:
            start = cleaned.find("{")
            end = cleaned.rfind("}") + 1
            if start >= 0 and end > start:
                result = json.loads(cleaned[start:end])
                claims = _extract_claims(result)
                if claims:
                    return claims
        except (json.JSONDecodeError, KeyError, TypeError):
            pass

        # 策略3：截断恢复——用正则逐条提取已完成的 claim 对象
        try:
            pattern = r'\{\s*"claim"\s*:\s*"([^"]*)"\s*,\s*"supported"\s*:\s*(true|false)\s*\}'
            matches = re.findall(pattern, cleaned, re.IGNORECASE)
            if matches:
                claims = [{"claim": m[0], "supported": m[1].lower() == "true"} for m in matches]
                logger.info(f"忠实度截断恢复成功，提取 {len(claims)} 条声明")
                return claims
        except (ValueError, IndexError):
            pass

        logger.warning(f"忠实度批量结果解析失败: {text[:200]}")
        return []

    def _fallback(self, answer: str) -> list[dict]:
        """LLM 不可用时的降级：按句号分句，默认全部不支持"""
        sentences = [s.strip() for s in answer.replace("！", "。").replace("？", "。").split("。") if len(s.strip()) > 5]
        if not sentences:
            sentences = [answer]
        return [{"claim": s, "supported": False} for s in sentences[:20]]

    async def _fallback_sequential(self, answer: str, contexts: str) -> list[dict]:
        """批量调用失败时的降级：使用旧的逐条模式"""
        try:
            # 提取声明
            extract_prompt = await self._prompt_manager.get_prompt(
                "rag.eval.metric.faithfulness_extract_claims",
                variables={"answer": answer},
            )
            llm = await self._llm_factory.create("rag_eval", "langchain")
            response = await llm.chat(LLMRequest(
                messages=[LLMMessage(role="user", content=extract_prompt)],
                timeout=120,
            ))

            text = response.content
            start = text.find("[")
            end = text.rfind("]") + 1
            if start >= 0 and end > start:
                claims = json.loads(text[start:end])
            else:
                claims = [s.strip() for s in text.split("\n") if len(s.strip()) > 10][:20]

            if not claims:
                return []

            # 逐条验证
            results = []
            for claim in claims:
                try:
                    verify_prompt = await self._prompt_manager.get_prompt(
                        "rag.eval.metric.faithfulness_verify_claim",
                        variables={"claim": str(claim), "contexts": contexts},
                    )
                    resp = await llm.chat(LLMRequest(
                        messages=[LLMMessage(role="user", content=verify_prompt)],
                        timeout=120,
                    ))
                    verdict = resp.content.lower().strip()
                    supported = any(kw in verdict for kw in ("支持", "正确", "yes", "true"))
                    results.append({"claim": str(claim), "supported": supported})
                except Exception:
                    results.append({"claim": str(claim), "supported": False})

            return results

        except Exception as e:
            logger.error(f"忠实度降级模式也失败: {e}")
            return self._fallback(answer)
