"""
高效去重引擎 (Phase D-1/D-2)

结合 content_hash 精确去重 (O(n)) 和 MinHash 近似去重 (O(n log n))，
替代原有 O(n²) 的 SequenceMatcher 比较。
"""

import hashlib
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from src.utils.logger import logger

try:
    from datasketch import MinHash, MinHashLSH

    DATASKETCH_AVAILABLE = True
except ImportError:
    DATASKETCH_AVAILABLE = False
    MinHash = None
    MinHashLSH = None
    logger.warning("datasketch not installed. MinHash dedup will be unavailable.")


@dataclass
class DedupResult:
    """去重结果"""

    items: List[Dict[str, Any]]
    exact_dedup_count: int = 0
    minhash_dedup_count: int = 0
    total_removed: int = 0


class DedupEngine:
    """高效去重引擎"""

    def __init__(
        self,
        minhash_num_perm: int = 128,
        minhash_threshold: float = 0.7,
        use_minhash: bool = True,
    ):
        self.minhash_num_perm = minhash_num_perm
        self.minhash_threshold = minhash_threshold
        self.use_minhash = use_minhash and DATASKETCH_AVAILABLE

        if self.use_minhash:
            logger.info(
                f"MinHash 近似去重已启用，num_perm={minhash_num_perm}, threshold={minhash_threshold}"
            )
        else:
            logger.info("MinHash 近似去重未启用（依赖缺失或配置关闭）")

    def deduplicate(
        self,
        items: List[Dict[str, Any]],
        content_key: str = "content",
        score_key: str = "relevance_score",
    ) -> DedupResult:
        """
        执行两步去重：
        1. content_hash 精确去重 (O(n))
        2. MinHash 近似去重 (O(n log n))

        Args:
            items: 待去重的结果列表
            content_key: 内容字段名
            score_key: 分数字段名

        Returns:
            DedupResult: 去重结果
        """
        if not items:
            return DedupResult(items=[])

        exact_dedup_count = 0
        minhash_dedup_count = 0

        # Step 1: content_hash 精确去重 (O(n))
        deduped_items = self._exact_dedup(items, content_key, score_key)
        exact_dedup_count = len(items) - len(deduped_items)

        # Step 2: MinHash 近似去重 (O(n log n))
        if self.use_minhash and len(deduped_items) > 1:
            deduped_items = self._minhash_dedup(deduped_items, content_key, score_key)
            minhash_dedup_count = len(deduped_items) - len(deduped_items)

        total_removed = exact_dedup_count + minhash_dedup_count

        if total_removed > 0:
            logger.info(
                f"去重完成：{len(items)} -> {len(deduped_items)} 个结果，"
                f"精确去重 {exact_dedup_count}，MinHash 去重 {minhash_dedup_count}"
            )

        return DedupResult(
            items=deduped_items,
            exact_dedup_count=exact_dedup_count,
            minhash_dedup_count=minhash_dedup_count,
            total_removed=total_removed,
        )

    def _exact_dedup(
        self,
        items: List[Dict[str, Any]],
        content_key: str,
        score_key: str,
    ) -> List[Dict[str, Any]]:
        """
        content_hash 精确去重 (O(n))

        使用 dict 按 content_hash 去重，保留分数更高的条目。
        """
        seen: Dict[str, Dict[str, Any]] = {}

        for item in items:
            content = item.get(content_key, "")
            content_hash = self._compute_hash(content)

            if content_hash in seen:
                existing_score = seen[content_hash].get(score_key, 0) or 0
                current_score = item.get(score_key, 0) or 0
                if current_score > existing_score:
                    seen[content_hash] = item
            else:
                seen[content_hash] = item

        return list(seen.values())

    def _minhash_dedup(
        self,
        items: List[Dict[str, Any]],
        content_key: str,
        score_key: str,
    ) -> List[Dict[str, Any]]:
        """
        MinHash 近似去重 (O(n log n))

        使用 LSH 分桶，仅桶内比较，避免 O(n²)。
        """
        if not DATASKETCH_AVAILABLE:
            return items

        try:
            num_bands = self._calculate_bands(
                self.minhash_num_perm, self.minhash_threshold
            )
            lsh = MinHashLSH(threshold=self.minhash_threshold, num_bands=num_bands)

            minhashes: List[Tuple[int, MinHash]] = []

            for idx, item in enumerate(items):
                content = item.get(content_key, "")
                minhash = self._compute_minhash(content)
                minhashes.append((idx, minhash))
                lsh.insert(str(idx), minhash)

            duplicate_indices: Set[int] = set()

            for idx, minhash in minhashes:
                if idx in duplicate_indices:
                    continue

                similar_keys = lsh.query(minhash)
                for key in similar_keys:
                    similar_idx = int(key)
                    if similar_idx != idx and similar_idx not in duplicate_indices:
                        duplicate_indices.add(similar_idx)

            deduped_items = [
                item for idx, item in enumerate(items) if idx not in duplicate_indices
            ]

            return deduped_items

        except Exception as e:
            logger.warning(f"MinHash 去重失败: {e}，返回原始结果")
            return items

    def _compute_hash(self, content: str) -> str:
        """计算内容 MD5 哈希"""
        return hashlib.md5(content.encode("utf-8")).hexdigest()

    def _compute_minhash(self, content: str) -> "MinHash":
        """计算内容 MinHash 签名"""
        if MinHash is None:
            raise RuntimeError("MinHash not available")

        minhash = MinHash(num_perm=self.minhash_num_perm)

        words = self._tokenize(content)
        for word in words:
            minhash.update(word.encode("utf-8"))

        return minhash

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        """中文分词（简单按字符 + jieba 如果可用）"""
        try:
            import jieba

            return list(jieba.cut(text))
        except ImportError:
            return list(text)

    @staticmethod
    def _calculate_bands(num_perm: int, threshold: float) -> int:
        """计算 LSH band 数量"""
        if threshold <= 0 or threshold >= 1:
            return num_perm // 4

        rows = int(round(num_perm ** (1 - threshold)))
        bands = num_perm // rows
        return max(1, min(bands, num_perm))
