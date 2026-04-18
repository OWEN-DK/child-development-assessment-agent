"""BM25/向量分数校准器"""

import math
from typing import List, Dict, Tuple
from src.utils.logger import logger


class ScoreCalibrator:
    """BM25/向量分数校准器"""

    def __init__(
        self,
        sigmoid_midpoint: float = 0.5,
        sigmoid_steepness: float = 10.0,
        min_samples: int = 3,
    ):
        """
        Args:
            sigmoid_midpoint: Sigmoid 中点
            sigmoid_steepness: Sigmoid 陡峭程度
            min_samples: Min-Max 归一化最小样本数阈值
        """
        self.sigmoid_midpoint = sigmoid_midpoint
        self.sigmoid_steepness = sigmoid_steepness
        self.min_samples = min_samples

    def calibrate_scores(self, scores: List[float]) -> List[float]:
        """
        对分数列表进行 Min-Max 归一化 + Sigmoid 校准

        Args:
            scores: 原始分数列表

        Returns:
            校准后的分数列表 [0, 1]
        """
        if not scores:
            return []

        # Step 1: Min-Max 归一化
        normalized = self._min_max_normalize(scores)

        # Step 2: Sigmoid 校准
        calibrated = [self._sigmoid(s) for s in normalized]

        return calibrated

    def calibrate_and_merge(
        self,
        bm25_scores: List[float],
        vector_scores: List[float],
        bm25_weight: float = 0.5,
        vector_weight: float = 0.5,
    ) -> List[float]:
        """
        校准并融合 BM25 和向量分数

        Args:
            bm25_scores: BM25 原始分数列表
            vector_scores: 向量原始分数列表
            bm25_weight: BM25 权重
            vector_weight: 向量权重

        Returns:
            融合后的分数列表（与输入顺序对应）
        """
        # Step 1: 分别归一化
        bm25_normalized = self._min_max_normalize(bm25_scores)
        vector_normalized = self._min_max_normalize(vector_scores)

        # Step 2: 统一 Sigmoid 校准
        bm25_calibrated = [self._sigmoid(s) for s in bm25_normalized]
        vector_calibrated = [self._sigmoid(s) for s in vector_normalized]

        # Step 3: 加权融合
        merged = []
        for b, v in zip(bm25_calibrated, vector_calibrated):
            merged.append(b * bm25_weight + v * vector_weight)

        return merged

    def calibrate_and_compare(
        self, bm25_scores: List[float], vector_scores: List[float]
    ) -> Dict[str, float]:
        """
        校准并比较 BM25 与向量分数的差异

        Returns:
            包含最大差异、平均差异等统计信息的字典
        """
        bm25_calibrated = self.calibrate_scores(bm25_scores)
        vector_calibrated = self.calibrate_scores(vector_scores)

        # 计算差异（取相同索引位置，假设已按相关性排序）
        min_len = min(len(bm25_calibrated), len(vector_calibrated))
        if min_len == 0:
            return {"max_diff": 0.0, "avg_diff": 0.0}

        diffs = [abs(bm25_calibrated[i] - vector_calibrated[i]) for i in range(min_len)]

        return {
            "max_diff": max(diffs),
            "avg_diff": sum(diffs) / len(diffs),
            "bm25_range": (min(bm25_calibrated), max(bm25_calibrated)),
            "vector_range": (min(vector_calibrated), max(vector_calibrated)),
        }

    def _min_max_normalize(
        self, scores: List[float], min_samples: int = None
    ) -> List[float]:
        """
        Min-Max 归一化到 [0, 1]

        Args:
            scores: 原始分数列表
            min_samples: 最小样本数阈值，低于此值时不进行归一化（默认使用构造函数的 min_samples）

        Returns:
            归一化后的分数列表
        """
        if min_samples is None:
            min_samples = self.min_samples

        if not scores:
            return []

        # 样本数不足时，不进行归一化，返回原始分数
        if len(scores) < min_samples:
            logger.debug(
                f"Min-Max 归一化跳过：样本数 {len(scores)} < 最小阈值 {min_samples}"
            )
            return scores

        min_s = min(scores)
        max_s = max(scores)
        if max_s == min_s:
            return [0.5] * len(scores)

        return [(s - min_s) / (max_s - min_s) for s in scores]

    def _sigmoid(self, score: float) -> float:
        """统一 Sigmoid 校准"""
        return 1 / (
            1 + math.exp(-self.sigmoid_steepness * (score - self.sigmoid_midpoint))
        )
