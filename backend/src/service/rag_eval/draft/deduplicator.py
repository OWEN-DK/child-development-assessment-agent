"""DraftDeduplicator - 语义去重"""

from typing import Optional

from src.schemas.rag_eval.draft import DraftCreate
from src.config.core.manager import ConfigManager
from src.repository.rag_eval.draft_repository import DraftRepository
from src.utils.embedding_helper import EmbeddingHelper
from src.utils.logger import logger


class DraftDeduplicator:
    """语义去重——过滤语义重复的草稿"""

    def __init__(
        self, embedding_helper: Optional[EmbeddingHelper] = None,
        draft_repository: Optional[DraftRepository] = None,
        config_cache: Optional[ConfigManager] = None,
    ):
        self._emb = embedding_helper
        self._repo = draft_repository
        self._config = config_cache or ConfigManager()

    async def deduplicate(
        self, drafts_with_scores: list[tuple[DraftCreate, float]],
        source_document_id: Optional[str] = None,
    ) -> list[tuple[DraftCreate, float]]:
        """去重：内部去重 + 外部去重（与已有草稿对比）"""
        if not drafts_with_scores or not self._emb:
            return drafts_with_scores

        threshold = self._config.get_config_value("rag.eval.draft.similarity_threshold", 0.85)
        texts = [d.query or (d.description or "") for d, _ in drafts_with_scores]
        try:
            embs = await self._emb.embed_batch(texts)
        except Exception as e:
            logger.error(f"Embedding 失败: {e}")
            return drafts_with_scores

        items = [(d, s, e) for (d, s), e in zip(drafts_with_scores, embs)]
        deduped = self._internal_dedup(items, threshold)

        if source_document_id and self._repo:
            deduped = await self._external_dedup(deduped, source_document_id, threshold)

        logger.info(f"去重: {len(drafts_with_scores)} → {len(deduped)}")
        return deduped

    def _internal_dedup(
        self, items: list[tuple[DraftCreate, float, list[float]]], threshold: float,
    ) -> list[tuple[DraftCreate, float]]:
        """内部去重：保留忠实度分数较高的"""
        if not self._emb:
            return [(d, s) for d, s, _ in items]
        kept = []
        for i, (d_a, s_a, e_a) in enumerate(items):
            if not e_a:
                kept.append((d_a, s_a))
                continue
            if not any(
                self._emb.cosine_similarity(e_a, e_b) >= threshold
                for j, (_, _, e_b) in enumerate(items) if j < i and e_b
            ):
                kept.append((d_a, s_a))
        return kept

    async def _external_dedup(
        self, items: list[tuple[DraftCreate, float]], source_document_id: str, threshold: float,
    ) -> list[tuple[DraftCreate, float]]:
        """与已有草稿的语义相似度比较"""
        try:
            existing = await self._repo.get_by_source_document(source_document_id, limit=500)
            if not existing:
                return items
            ex_embs = await self._emb.embed_batch(
                [d.query or (d.description or "") for d in existing]
            )
            filtered = []
            for draft, score in items:
                e = await self._emb.embed_text(draft.query or (draft.description or ""))
                if not e or any(
                    self._emb.cosine_similarity(e, ex) >= threshold
                    for ex in ex_embs if ex
                ):
                    continue
                filtered.append((draft, score))
            return filtered
        except Exception as e:
            logger.error(f"外部去重失败: {e}")
            return items
