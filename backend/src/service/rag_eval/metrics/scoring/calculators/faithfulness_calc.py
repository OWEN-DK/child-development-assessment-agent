"""L2 忠实度计算器——FaithfulnessCalculator（灵感来自 RAGAS）"""

import json
from typing import Optional

from src.core.llm.factory import LLMServiceFactory
from src.core.prompt_impl.facade import PromptManager
from src.schemas.rag_eval.metrics import MetricInput, MetricOutput
from src.service.rag_eval.metrics.scoring.base import MetricCalculator
from src.utils.logger import logger


class FaithfulnessCalculator(MetricCalculator):
    """忠实度（灵感来自 RAGAS）

    计算: 被上下文支持的声明数 / 总声明数
    阈值: ≥ 0.8

    流程：
    1. 使用 LLM 从 actual_answer 中提取声明（claims）
    2. 对每个声明，判断是否被 retrieved_contexts 支持
    3. supported_claims / total_claims
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

        # 步骤1：使用 LLM 提取声明
        claims = await self._extract_claims(input_data.actual_answer)
        if not claims:
            return MetricOutput(score=0.0, passed=False, threshold=threshold, details={"reason": "未能提取声明", "claims": []})

        # 步骤2：验证每个声明
        contexts_text = "\n---\n".join(input_data.retrieved_contexts)
        supported = 0
        claim_results = []

        for claim in claims:
            verdict = await self._verify_claim(claim, contexts_text)
            claim_results.append({"claim": claim, "supported": verdict})
            if verdict:
                supported += 1

        score = supported / len(claims)
        return MetricOutput(
            score=round(score, 4),
            passed=score >= threshold,
            threshold=threshold,
            details={"total_claims": len(claims), "supported_claims": supported, "claim_results": claim_results},
        )

    async def _extract_claims(self, answer: str) -> list[str]:
        """使用 LLM 从答案中提取声明列表"""
        if not self._llm_factory:
            return self._fallback_extract_claims(answer)

        try:
            prompt = await self._prompt_manager.get_prompt(
                "rag.eval.metric.faithfulness_extract_claims",
                variables={"answer": answer},
            )
            llm = await self._llm_factory.create("rag_eval", "langchain")
            response = await llm.chat(messages=[{"role": "user", "content": prompt}])

            # 尝试解析 JSON 数组
            text = response.get("content", "") if isinstance(response, dict) else str(response)
            # 提取 JSON 数组
            start = text.find("[")
            end = text.rfind("]") + 1
            if start >= 0 and end > start:
                claims = json.loads(text[start:end])
                if isinstance(claims, list):
                    return [str(c) for c in claims]
            # 按行分割作为兜底
            lines = [line.strip("- •").strip() for line in text.split("\n") if line.strip() and len(line.strip()) > 10]
            return lines[:20] if lines else [answer]
        except Exception as e:
            logger.warning(f"LLM 提取声明失败: {e}，使用降级策略")
            return self._fallback_extract_claims(answer)

    def _fallback_extract_claims(self, answer: str) -> list[str]:
        """LLM 不可用时的降级：按句号分句作为声明"""
        sentences = [s.strip() for s in answer.replace("！", "。").replace("？", "。").split("。") if len(s.strip()) > 5]
        return sentences if sentences else [answer]

    async def _verify_claim(self, claim: str, contexts: str) -> bool:
        """使用 LLM 验证声明是否被上下文支持"""
        if not self._llm_factory:
            return False  # LLM 不可用时默认不支持

        try:
            prompt = await self._prompt_manager.get_prompt(
                "rag.eval.metric.faithfulness_verify_claim",
                variables={"claim": claim, "contexts": contexts},
            )
            llm = await self._llm_factory.create("rag_eval", "langchain")
            response = await llm.chat(messages=[{"role": "user", "content": prompt}])

            text = response.get("content", "") if isinstance(response, dict) else str(response)
            return text.lower().strip().startswith(("yes", "是", "true", "支持"))
        except Exception as e:
            logger.warning(f"LLM 验证声明失败: {e}")
            return False
