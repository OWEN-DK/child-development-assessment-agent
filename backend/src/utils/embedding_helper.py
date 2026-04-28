"""Embedding 缓存+计算工具

封装 Embedding 模型调用，提供批量计算和缓存功能。
"""

import time
from typing import Optional

from src.utils.similarity import cosine_similarity as _cosine_similarity


class EmbeddingHelper:
    """Embedding 缓存+计算工具

    封装 Embedding 模型调用，提供批量计算和缓存功能。
    当前为基础设施层占位实现，具体嵌入模型调用将在 Phase 1-7 中实现。
    """

    def __init__(
        self,
        cache_size: int = 1000,
        ttl_seconds: int = 3600,
    ):
        self._cache: dict[str, tuple[list[float], float]] = {}
        self._cache_size = cache_size
        self._ttl_seconds = ttl_seconds

    def _clean_expired(self) -> None:
        """清理过期缓存"""
        now = time.time()
        expired_keys = [
            k for k, (_, ts) in self._cache.items()
            if now - ts > self._ttl_seconds
        ]
        for k in expired_keys:
            del self._cache[k]

    def _evict_if_needed(self) -> None:
        """缓存满时淘汰最早条目"""
        if len(self._cache) >= self._cache_size:
            oldest_key = min(self._cache, key=lambda k: self._cache[k][1])
            del self._cache[oldest_key]

    async def embed_text(self, text: str) -> list[float]:
        """计算单个文本的 Embedding 向量

        Args:
            text: 输入文本

        Returns:
            Embedding 向量（float 列表）
        """
        if not text.strip():
            return []
        self._clean_expired()
        cached = self._cache.get(text)
        if cached:
            embedding, _ = cached
            return embedding
        # 占位实现：Phase 1-7 中替换为真实嵌入模型调用
        result = await self._do_embed(text)
        self._evict_if_needed()
        self._cache[text] = (result, time.time())
        return result

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """批量计算 Embedding 向量

        Args:
            texts: 输入文本列表

        Returns:
            Embedding 向量列表
        """
        results = []
        for text in texts:
            embedding = await self.embed_text(text)
            results.append(embedding)
        return results

    async def _do_embed(self, text: str) -> list[float]:
        """实际嵌入计算（占位实现，Phase 1-7 替换）"""
        # 占位：返回简单哈希向量，后续阶段接入真实 Embedding 模型
        import hashlib
        hash_bytes = hashlib.sha256(text.encode("utf-8")).digest()
        return [float(b) / 255.0 for b in hash_bytes[:32]]

    def cosine_similarity(self, a: list[float], b: list[float]) -> float:
        """计算两个向量的余弦相似度"""
        return _cosine_similarity(a, b)

    @property
    def cache_hit_count(self) -> int:
        """缓存命中次数（调试用）"""
        return len(self._cache)
