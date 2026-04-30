"""FaithfulnessChecker - 验证草稿忠实度"""

import asyncio
import json
from typing import Awaitable, Callable, Optional

from json_repair import repair_json as _repair

from src.schemas.rag_eval.draft import DraftCreate
from src.schemas.llm import LLMMessage, LLMRequest
from src.config.core.manager import ConfigManager
from src.core.llm.factory import LLMServiceFactoryCompat
from src.utils.embedding_helper import EmbeddingHelper
from src.utils.logger import logger


class FaithfulnessChecker:
    """验证草稿忠实度——embedding 相似度 + LLM 辅助双重校验"""

    def __init__(
        self,
        embedding_helper: Optional[EmbeddingHelper] = None,
        config_cache: Optional[ConfigManager] = None,
    ):
        self._embedding = embedding_helper
        self._config = config_cache or ConfigManager()

    async def check(self, draft: DraftCreate, source_content: str) -> float:
        """检查单个草稿忠实度，返回 0-1 评分"""
        # 优先使用 answer_points 构建比较文本
        if draft.answer_points:
            compare_text = "。".join(draft.answer_points)
        else:
            compare_text = draft.description or ""

        compare_text = compare_text[:500]
        if not compare_text.strip() or not source_content.strip():
            return 0.5

        emb_score = await self._embedding_faithfulness_async(
            compare_text, source_content[:1500]
        )

        if emb_score < 0.6:
            try:
                llm_score = await self._llm_faithfulness_check(
                    compare_text, source_content[:1500]
                )
                return max(emb_score, llm_score)
            except Exception as e:
                logger.error(f"LLM 忠实度校验失败: {e}")

        return emb_score

    async def batch_check(
        self, drafts: list[DraftCreate],
        progress_callback: Optional[Callable[[int, int], Awaitable[None]]] = None,
        semaphore: Optional[asyncio.Semaphore] = None,
    ) -> list[tuple[DraftCreate, float]]:
        """批量校验，返回 [(draft, score), ...]"""
        if not drafts:
            return []

        sem = semaphore or asyncio.Semaphore(
            self._config.get_config_value("rag.eval.draft.concurrency", 15)
        )

        async def _one(d: DraftCreate) -> tuple[DraftCreate, float]:
            async with sem:
                src = (d.source_content_snippet or "")[:3000]
                return (d, await self.check(d, src))

        all_coros = [_one(d) for d in drafts]
        total = len(all_coros)
        results = []
        completed = 0
        for coro in asyncio.as_completed(all_coros):
            item = await coro
            results.append(item)
            completed += 1
            if progress_callback:
                await progress_callback(completed, total)

        threshold = self._config.get_config_value("rag.eval.draft.faithfulness_threshold", 0.7)
        low = sum(1 for _, s in results if s < threshold)
        if low:
            logger.warning(f"忠实度校验: {low}/{len(results)} 低于阈值")
        return list(results)

    async def _embedding_faithfulness_async(self, draft_description: str, source_content: str) -> float:
        """Embedding 余弦相似度快速评分（异步）"""
        if not self._embedding:
            return 0.5
        try:
            e1 = await self._embedding.embed_text(draft_description[:500])
            e2 = await self._embedding.embed_text(source_content[:500])
            if not e1 or not e2:
                return 0.5
            return self._embedding.cosine_similarity(e1, e2)
        except Exception as e:
            logger.debug(f"Embedding 计算失败: {e}")
            return 0.5

    async def _llm_faithfulness_check(self, draft_text: str, source_content: str) -> float:
        """LLM 深度忠实度校验，返回 0-1"""
        prompt = f"""评估答案要点是否忠实于原文。

原文: {source_content[:1500]}

答案要点: {draft_text[:800]}

请判断答案要点中的内容是否都能在原文中找到依据，返回 JSON:
{{"faithfulness_score": 0.85, "reason": "..."}}"""

        model = self._config.get_config_value("rag.eval.draft.llm_model", "") or "qwen-plus"
        llm = LLMServiceFactoryCompat.create(
            model_name=model,
            temperature=self._config.get_config_value("rag.eval.draft.temperature", 0.3),
            max_tokens=512,
        )
        resp = await llm.chat(LLMRequest(
            messages=[LLMMessage(role="user", content=prompt)],
            model_name=model,
        ))

        try:
            parsed = json.loads(resp.content.strip())
        except json.JSONDecodeError:
            parsed = json.loads(_repair(resp.content.strip()))

        return max(0.0, min(1.0, float(parsed.get("faithfulness_score", 0.5))))
