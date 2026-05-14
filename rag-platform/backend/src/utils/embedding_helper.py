"""Embedding 缓存+计算工具

封装 Embedding 模型调用，提供批量计算和缓存功能。
使用 DashScope text-embedding-v4 作为默认嵌入模型。
"""

import time
from typing import Optional

from src.utils.similarity import cosine_similarity as _cosine_similarity
from src.utils.logger import logger


class EmbeddingHelper:
    """Embedding 缓存+计算工具

    封装 DashScope Embedding 模型调用，提供批量计算和内存缓存。
    当未配置 model_name 或 api_key 时回退到 SHA256 占位符（仅用于测试）。
    """

    def __init__(
        self,
        cache_size: int = 1000,
        ttl_seconds: int = 3600,
        model_name: Optional[str] = None,
        api_key: Optional[str] = None,
        embed_batch_size: int = 10,
    ):
        self._cache: dict[str, tuple[list[float], float]] = {}
        self._cache_size = cache_size
        self._ttl_seconds = ttl_seconds
        self._embed_model = None
        if model_name and api_key:
            from src.core.embedding import SafeDashScopeEmbedding
            self._embed_model = SafeDashScopeEmbedding(
                model_name=model_name,
                api_key=api_key,
                embed_batch_size=embed_batch_size,
            )

    def _clean_expired(self) -> None:
        now = time.time()
        expired_keys = [
            k for k, (_, ts) in self._cache.items()
            if now - ts > self._ttl_seconds
        ]
        for k in expired_keys:
            del self._cache[k]

    def _evict_if_needed(self) -> None:
        if len(self._cache) >= self._cache_size:
            oldest_key = min(self._cache, key=lambda k: self._cache[k][1])
            del self._cache[oldest_key]

    async def embed_text(self, text: str) -> list[float]:
        """计算单个文本的 Embedding 向量"""
        if not text.strip():
            return []
        self._clean_expired()
        cached = self._cache.get(text)
        if cached:
            return cached[0]
        result = await self._do_embed(text)
        self._evict_if_needed()
        self._cache[text] = (result, time.time())
        return result

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """批量计算 Embedding 向量，优先使用真实批量 API"""
        if not texts:
            return []
        self._clean_expired()

        results: list[Optional[list[float]]] = [None] * len(texts)
        uncached_indices: list[int] = []
        uncached_texts: list[str] = []

        for i, text in enumerate(texts):
            if not text.strip():
                results[i] = []
                continue
            cached = self._cache.get(text)
            if cached:
                results[i] = cached[0]
            else:
                uncached_indices.append(i)
                uncached_texts.append(text)

        if not uncached_texts:
            return [r if r is not None else [] for r in results]

        if self._embed_model:
            try:
                embeddings = await self._embed_model.aget_text_embedding_batch(uncached_texts)
                for i, emb in zip(uncached_indices, embeddings):
                    results[i] = emb
                    self._evict_if_needed()
                    self._cache[uncached_texts[uncached_indices.index(i)]] = (emb, time.time())
            except Exception as e:
                logger.warning(f"批量 Embedding 失败，回退到逐条计算: {e}")
                for i, text in zip(uncached_indices, uncached_texts):
                    results[i] = await self._do_embed(text)
                    self._evict_if_needed()
                    self._cache[text] = (results[i], time.time())  # type: ignore[index]
        else:
            for i, text in zip(uncached_indices, uncached_texts):
                results[i] = await self._do_embed(text)
                self._evict_if_needed()
                self._cache[text] = (results[i], time.time())  # type: ignore[index]

        return [r if r is not None else [] for r in results]

    async def _do_embed(self, text: str) -> list[float]:
        """实际嵌入计算，优先使用 DashScope，不可用时回退 SHA256 占位符"""
        if self._embed_model:
            try:
                return await self._embed_model._aget_text_embedding(text)
            except Exception as e:
                logger.warning(f"DashScope Embedding 失败，使用占位符: {e}")
        import hashlib
        hash_bytes = hashlib.sha256(text.encode("utf-8")).digest()
        return [float(b) / 255.0 for b in hash_bytes[:32]]

    def cosine_similarity(self, a: list[float], b: list[float]) -> float:
        return _cosine_similarity(a, b)

    @property
    def cache_hit_count(self) -> int:
        return len(self._cache)
