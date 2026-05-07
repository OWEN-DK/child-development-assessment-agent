"""L2 落地度计算器——GroundednessCalculator（灵感来自 TruLens）

优化：将逐句评分合并为单次 LLM 调用，从 M 次降至 1 次。
"""

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

    流程（单次 LLM 调用）：
    1. 将 actual_answer 拆分为句子
    2. 使用批量 prompt 一次性评估所有句子的落地度
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

        contexts_text = "\n---\n".join(input_data.retrieved_contexts)

        # 步骤2：单次 LLM 调用，批量评分
        sentence_scores = await self._batch_judge(sentences, contexts_text)

        if not sentence_scores:
            return MetricOutput(score=0.0, passed=False, threshold=threshold, details={"reason": "批量评分失败"})

        score = sum(sentence_scores) / len(sentence_scores) if sentence_scores else 0.0
        sentence_results = [
            {"sentence": s, "support_score": round(sc, 4)}
            for s, sc in zip(sentences[:len(sentence_scores)], sentence_scores)
        ]

        return MetricOutput(
            score=round(score, 4),
            passed=score >= threshold,
            threshold=threshold,
            details={"sentence_count": len(sentences), "sentence_results": sentence_results},
        )

    def _split_sentences(self, text: str) -> list[str]:
        """将文本拆分为句子"""
        for sep in ["。", "！", "？", ".", "!", "?", "\n"]:
            text = text.replace(sep, "||")
        sentences = [s.strip() for s in text.split("||") if len(s.strip()) > 3]
        return sentences[:30]

    async def _batch_judge(self, sentences: list[str], contexts: str) -> list[float]:
        """单次 LLM 调用：批量评估所有句子的落地度（解析失败自动重试 1 次）"""
        if not self._llm_factory:
            return [0.0] * len(sentences)

        sentences_json = json.dumps(sentences, ensure_ascii=False)
        prompt = await self._prompt_manager.get_prompt(
            "rag.eval.metric.groundedness_batch",
            variables={"sentences_json": sentences_json, "contexts": contexts},
        )

        for attempt in range(2):
            try:
                llm = await self._llm_factory.create("rag_eval", "langchain")
                response = await llm.chat(LLMRequest(
                    messages=[LLMMessage(role="user", content=prompt)],
                    timeout=120,
                ))
                scores = self._parse_batch_scores(response.content, len(sentences))
                if scores:
                    return scores
                logger.warning(f"落地度批量解析为空（第 {attempt + 1} 次），重试")
            except Exception as e:
                logger.warning(f"落地度批量调用失败（第 {attempt + 1} 次）: {e}")

        logger.warning("落地度批量调用 2 次均失败，降级为逐句模式")
        return await self._fallback_sequential(sentences, contexts)

    def _parse_batch_scores(self, text: str, expected_count: int) -> list[float]:
        """解析 LLM 返回的批量评分 JSON（支持截断恢复）"""
        import re
        # 清理 markdown 代码块包裹
        cleaned = re.sub(r'```(?:json)?\s*', '', text).strip().rstrip('`').strip()

        def _extract_scores(data: list) -> list[float]:
            """从 JSON 数组中提取分数列表"""
            scores = []
            sorted_data = sorted(data, key=lambda x: x.get("index", 0))
            for item in sorted_data:
                if isinstance(item, dict) and "score" in item:
                    scores.append(max(0.0, min(1.0, float(item["score"]))))
            return scores

        # 策略1：直接解析
        try:
            result = json.loads(cleaned)
            if isinstance(result, list):
                scores = _extract_scores(result)
                if scores:
                    return scores
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            pass

        # 策略2：提取 JSON 子串
        try:
            start = cleaned.find("[")
            end = cleaned.rfind("]") + 1
            if start >= 0 and end > start:
                result = json.loads(cleaned[start:end])
                if isinstance(result, list):
                    scores = _extract_scores(result)
                    if scores:
                        return scores
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            pass

        # 策略3：截断恢复——用正则逐条提取已完成的对象
        try:
            pattern = r'\{\s*"index"\s*:\s*(\d+)\s*,\s*"score"\s*:\s*([\d.]+)\s*\}'
            matches = re.findall(pattern, cleaned)
            if matches:
                scores = [max(0.0, min(1.0, float(m[1]))) for m in sorted(matches, key=lambda x: int(x[0]))]
                if scores:
                    logger.info(f"落地度截断恢复成功，提取 {len(scores)}/{expected_count} 条分数")
                    return scores
        except (ValueError, IndexError):
            pass

        logger.warning(f"落地度批量结果解析失败: {text[:200]}")
        return []

    async def _fallback_sequential(self, sentences: list[str], contexts: str) -> list[float]:
        """批量调用失败时的降级：使用旧的逐句模式"""
        scores = []
        for sentence in sentences:
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
                score = self._parse_single_score(response.content)
                scores.append(score)
            except Exception as e:
                logger.warning(f"落地度逐句评分失败: {e}")
                scores.append(0.0)
        return scores

    def _parse_single_score(self, text: str) -> float:
        """解析单个分数"""
        import re
        labeled = re.search(r'(?:score|得分|分数|置信度|支持度)[：:\s]*([0-9]*\.?[0-9]+)', text, re.IGNORECASE)
        if labeled:
            score = float(labeled.group(1))
            if score > 1.0:
                score = score / 100.0
            return max(0.0, min(1.0, score))

        all_numbers = re.findall(r'(?<!\d)([01](?:\.[0-9]+)?|0?\.[0-9]+)(?!\d)', text)
        for n in all_numbers:
            val = float(n)
            if 0.0 <= val <= 1.0:
                return val

        text_lower = text.lower()
        if any(w in text_lower for w in ["完全支持", "fully", "strongly"]):
            return 0.85
        if any(w in text_lower for w in ["支持", "yes", "相符"]):
            return 0.75
        if any(w in text_lower for w in ["部分", "partially"]):
            return 0.5
        if any(w in text_lower for w in ["不支持", "no", "not"]):
            return 0.15
        return 0.5
