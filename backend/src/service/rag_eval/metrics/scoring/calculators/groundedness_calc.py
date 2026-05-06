"""L2 落地度计算器——GroundednessCalculator（灵感来自 TruLens）"""

import json
from typing import Optional

from src.core.llm.factory import LLMServiceFactory
from src.core.prompt_impl.facade import PromptManager
from src.schemas.llm import LLMMessage, LLMRequest
from src.schemas.rag_eval.metrics import MetricInput, MetricOutput
from src.service.rag_eval.metrics.scoring.base import MetricCalculator
from src.utils.logger import logger


class GroundednessCalculator(MetricCalculator):
    """落地度（灵感来自 TruLens）

    计算: 答案每句话在上下文中的溯源得分均值
    阈值: ≥ 0.75

    流程：
    1. 将 actual_answer 拆分为句子
    2. 对每句话，使用 LLM 判断其在 retrieved_contexts 中的支持程度（0-1）
    3. 取均值
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
        return "groundedness"

    @property
    def layer(self) -> int:
        return 2

    @property
    def description(self) -> str:
        return "落地度：答案每句话是否能从上下文溯源"

    async def calculate(self, input_data: MetricInput) -> MetricOutput:
        threshold = await self._get_threshold()

        if not input_data.actual_answer or not input_data.actual_answer.strip():
            return MetricOutput(score=0.0, passed=False, threshold=threshold, details={"reason": "答案为空"})

        if not input_data.retrieved_contexts:
            return MetricOutput(score=0.0, passed=False, threshold=threshold, details={"reason": "无检索上下文"})

        # 步骤1：拆分句子
        sentences = self._split_sentences(input_data.actual_answer)
        if not sentences:
            return MetricOutput(score=0.0, passed=False, threshold=threshold, details={"reason": "无法拆分为句子"})

        # 步骤2：逐句评判
        contexts_text = "\n---\n".join(input_data.retrieved_contexts)
        scores = []
        sentence_results = []

        for sentence in sentences:
            support_score = await self._judge_support(sentence, contexts_text)
            scores.append(support_score)
            sentence_results.append({"sentence": sentence, "support_score": round(support_score, 4)})

        score = sum(scores) / len(scores) if scores else 0.0
        return MetricOutput(
            score=round(score, 4),
            passed=score >= threshold,
            threshold=threshold,
            details={"sentence_count": len(sentences), "sentence_results": sentence_results},
        )

    def _split_sentences(self, text: str) -> list[str]:
        """将文本拆分为句子"""
        # 按中英文标点分句
        for sep in ["。", "！", "？", ".", "!", "?", "\n"]:
            text = text.replace(sep, "||")
        sentences = [s.strip() for s in text.split("||") if len(s.strip()) > 3]
        return sentences[:30]  # 限制最多 30 句，防止过长

    async def _judge_support(self, sentence: str, contexts: str) -> float:
        """使用 LLM 判断句子在上下文中的支持程度，返回 0-1 分数"""
        if not self._llm_factory:
            return 0.0

        try:
            prompt = await self._prompt_manager.get_prompt(
                "rag.eval.metric.groundedness",
                variables={"sentence": sentence, "contexts": contexts},
            )
            llm = await self._llm_factory.create("rag_eval", "langchain")
            response = await llm.chat(LLMRequest(
                messages=[LLMMessage(role="user", content=prompt)],
                timeout=120,
            ))

            text = response.content

            # 尝试从响应中解析 0-1 分数
            # 匹配类似 "score: 0.8" 或 "得分: 0.75" 或纯数字
            import re
            match = re.search(r'([0-9]*\.?[0-9]+)', text)
            if match:
                score = float(match.group(1))
                return max(0.0, min(1.0, score))
            # 如果包含肯定词，给高分
            if any(w in text.lower() for w in ["支持", "yes", "fully", "strongly", "完全", "充分"]):
                return 0.85
            if any(w in text.lower() for w in ["部分", "partially", "somewhat", "基本"]):
                return 0.5
            if any(w in text.lower() for w in ["不支持", "no", "not", "不相关", "无关", "不能"]):
                return 0.15
            return 0.5  # 默认中等
        except Exception as e:
            logger.warning(f"LLM 落地度判断失败: {e}")
            return 0.0
