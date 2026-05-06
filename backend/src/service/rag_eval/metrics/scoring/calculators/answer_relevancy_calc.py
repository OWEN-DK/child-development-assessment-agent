"""L2 答案相关性计算器——AnswerRelevancyCalculator（灵感来自 RAGAS）"""

import json
from typing import Optional

from src.core.llm.factory import LLMServiceFactory
from src.core.prompt_impl.facade import PromptManager
from src.schemas.llm import LLMMessage, LLMRequest
from src.schemas.rag_eval.metrics import MetricInput, MetricOutput
from src.service.rag_eval.metrics.scoring.base import MetricCalculator
from src.utils.embedding_helper import EmbeddingHelper
from src.utils.similarity import cosine_similarity
from src.utils.logger import logger


class AnswerRelevancyCalculator(MetricCalculator):
    """答案相关性（灵感来自 RAGAS）

    计算: 从答案反生成问题的平均 embedding 相似度
    阈值: ≥ 0.7

    流程：
    1. 使用 LLM 从 actual_answer 反生成 3 个可能的问题
    2. 计算每个生成问题与原始 query 的 embedding 余弦相似度
    3. 取均值
    """

    def __init__(
        self,
        llm_factory: Optional[LLMServiceFactory] = None,
        prompt_manager: Optional[PromptManager] = None,
        embedding_helper: Optional[EmbeddingHelper] = None,
        config_cache=None,
    ):
        super().__init__(config_cache)
        self._llm_factory = llm_factory
        self._prompt_manager = prompt_manager or PromptManager()
        self._embedding_helper = embedding_helper or EmbeddingHelper()

    @property
    def name(self) -> str:
        return "answer_relevancy"

    @property
    def layer(self) -> int:
        return 2

    @property
    def description(self) -> str:
        return "答案相关性：从答案反生成问题的 embedding 相似度均值"

    async def calculate(self, input_data: MetricInput) -> MetricOutput:
        threshold = await self._get_threshold()

        if not input_data.actual_answer or not input_data.actual_answer.strip():
            return MetricOutput(score=0.0, passed=False, threshold=threshold, details={"reason": "答案为空"})

        if not input_data.query or not input_data.query.strip():
            return MetricOutput(score=0.0, passed=False, threshold=threshold, details={"reason": "查询为空"})

        # 步骤1：从答案反生成问题
        generated_questions = await self._generate_questions(input_data.actual_answer)
        if not generated_questions:
            return MetricOutput(
                score=0.0, passed=False, threshold=threshold, details={"reason": "未能反生成问题", "generated_questions": []}
            )

        # 步骤2：计算 embedding 相似度
        try:
            original_embedding = await self._embedding_helper.embed_text(input_data.query)
            if not original_embedding:
                return MetricOutput(score=0.0, passed=False, threshold=threshold, details={"reason": "Embedding 计算失败"})

            similarities = []
            for q in generated_questions:
                q_embedding = await self._embedding_helper.embed_text(q)
                if q_embedding:
                    sim = cosine_similarity(original_embedding, q_embedding)
                    similarities.append(max(0.0, sim))

            if not similarities:
                return MetricOutput(score=0.0, passed=False, threshold=threshold, details={"reason": "相似度计算失败"})

            score = sum(similarities) / len(similarities)
        except Exception as e:
            logger.error(f"Embedding 相似度计算异常: {e}")
            return MetricOutput(score=0.0, passed=False, threshold=threshold, details={"reason": f"Embedding 异常: {str(e)}"})

        return MetricOutput(
            score=round(min(score, 1.0), 4),
            passed=score >= threshold,
            threshold=threshold,
            details={"generated_questions": generated_questions, "similarities": [round(s, 4) for s in similarities]},
        )

    async def _generate_questions(self, answer: str) -> list[str]:
        """使用 LLM 从答案反生成问题"""
        if not self._llm_factory:
            return self._fallback_generate_questions(answer)

        try:
            prompt = await self._prompt_manager.get_prompt(
                "rag.eval.metric.answer_relevancy_generate",
                variables={"answer": answer},
            )
            llm = await self._llm_factory.create("rag_eval", "langchain")
            response = await llm.chat(LLMRequest(
                messages=[LLMMessage(role="user", content=prompt)],
                timeout=120,
            ))

            text = response.content
            start = text.find("[")
            end = text.rfind("]") + 1
            if start >= 0 and end > start:
                questions = json.loads(text[start:end])
                if isinstance(questions, list):
                    return [str(q) for q in questions[:3]]
            lines = [line.strip("- •0123456789. ").strip() for line in text.split("\n") if line.strip() and "?" in line]
            return lines[:3] if lines else [f"问题: {answer[:50]}"]
        except Exception as e:
            logger.warning(f"LLM 反生成问题失败: {e}")
            return self._fallback_generate_questions(answer)

    def _fallback_generate_questions(self, answer: str) -> list[str]:
        """LLM 不可用时的降级：从答案切取关键词构造问题"""
        return [f"关于{answer[:30]}的问题"]
