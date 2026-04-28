"""相似度计算工具

提供 cosine、欧氏距离、Jaccard 等常用相似度计算函数。
"""

import math


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """计算两个向量的余弦相似度

    Args:
        a: 向量 A
        b: 向量 B

    Returns:
        余弦相似度，范围 [-1, 1]，相同方向为 1
    """
    if not a or not b or len(a) != len(b):
        return 0.0
    dot_product = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot_product / (norm_a * norm_b)


def euclidean_distance(a: list[float], b: list[float]) -> float:
    """计算两个向量的欧氏距离

    Args:
        a: 向量 A
        b: 向量 B

    Returns:
        欧氏距离，值越小越相似
    """
    if not a or not b or len(a) != len(b):
        return float("inf")
    squared_diff = sum((x - y) ** 2 for x, y in zip(a, b))
    return math.sqrt(squared_diff)


def jaccard_similarity(a: set, b: set) -> float:
    """计算两个集合的 Jaccard 相似度

    Args:
        a: 集合 A
        b: 集合 B

    Returns:
        Jaccard 相似度，范围 [0, 1]
    """
    if not a and not b:
        return 1.0
    intersection = a & b
    union = a | b
    if not union:
        return 0.0
    return len(intersection) / len(union)
