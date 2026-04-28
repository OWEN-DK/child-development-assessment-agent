"""FaithfulnessChecker - 验证草稿忠实度"""

import asyncio
import json
from typing import Optional

from json_repair import repair_json as _repair

from src.schemas.rag_eval.draft import DraftCreate
from src.schemas.llm import LLMMessage, LLMRequest
from src.config.core.manager import ConfigManager
from src.utils.embedding_helper import EmbeddingHelper
from src.utils.logger import logger


class FaithfulnessChecker:
    """验证草稿忠实度——embedding 相似度 + LLM 辅助双重校验"""

    def __init__(
        self,
        llm_factory=None,
        embedding_helper: Optional[EmbeddingHelper] = None,
        config_cache: Optional[ConfigManager] = None,
    ):
        self._llm_factory = llm_factory
        self._embedding = embedding_helper
        self._config = config_cache or ConfigManager()

    async def check(self, draft: DraftCreate, source_content: str) -> float:
        """检查单个草稿忠实度，返回 0-1 评分"""
        draft_text = draft.description or draft.query
        if not draft_text.strip() or not source_content.strip():
            return 0.0

        emb_score = self._embedding_faithfulness(draft_text, source_content)
        threshold = self._config.get_config_value("rag.eval.draft.faithfulness_threshold", 0.7)

        if emb_score >= threshold or not self._llm_factory:
            return emb_score

        try:
            llm_score = await self._llm_faithfulness_check(draft_text, source_content)
            return max(emb_score, llm_score)
        except Exception as e:
            logger.error(f"LLM 忠实度校验失败: {e}")
            return emb_score

    async def batch_check(self, drafts: list[DraftCreate]) -> list[tuple[DraftCreate, float]]:
        """批量校验，返回 [(draft, score), ...]"""
        if not drafts:
            return []

        concurrency = self._config.get_config_value("rag.eval.draft.concurrency", 3)
        sem = asyncio.Semaphore(concurrency)

        async def _one(d: DraftCreate) -> tuple[DraftCreate, float]:
            async with sem:
                src = (d.source_content_snippet or "")[:3000]
                return (d, await self.check(d, src))

        results = await asyncio.gather(*[_one(d) for d in drafts])

        threshold = self._config.get_config_value("rag.eval.draft.faithfulness_threshold", 0.7)
        low = sum(1 for _, s in results if s < threshold)
        if low:
            logger.warning(f"忠实度校验: {low}/{len(results)} 低于阈值")
        return list(results)

    def _embedding_faithfulness(self, draft_description: str, source_content: str) -> float:
        """Embedding 余弦相似度快速评分"""
        if not self._embedding:
            return 0.5
        try:
            import asyncio as _asyncio
            loop = _asyncio.get_event_loop()
            e1 = loop.run_until_complete(self._embedding.embed_text(draft_description[:500]))
            e2 = loop.run_until_complete(self._embedding.embed_text(source_content[:500]))
            if not e1 or not e2:
                return 0.5
            return self._embedding.cosine_similarity(e1, e2)
        except Exception as e:
            logger.debug(f"Embedding 计算失败: {e}")
            return 0.5

    async def _llm_faithfulness_check(self, draft_text: str, source_content: str) -> float:
        """LLM 深度忠实度校验，返回 0-1"""
        prompt = f"""评估草稿忠实度。源文档内容: {source_content[:1500]}
草稿: {draft_text[:800]}
返回 JSON: {{"faithfulness_score": 0.85, "reason": "..."}}"""

        llm = await self._llm_factory.create("rag_eval", "langchain")
        model = self._config.get_config_value("rag.eval.draft.llm_model", "")
        resp = await llm.chat(LLMRequest(
            messages=[LLMMessage(role="user", content=prompt)],
            model_name=model or "qwen3.5-plus",
            temperature=self._config.get_config_value("rag.eval.draft.temperature", 0.3),
            max_tokens=512,
        ))

        try:
            parsed = json.loads(resp.content.strip())
        except json.JSONDecodeError:
            parsed = json.loads(_repair(resp.content.strip()))

        return max(0.0, min(1.0, float(parsed.get("faithfulness_score", 0.5))))
