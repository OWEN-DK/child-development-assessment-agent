"""来源多样性重排 — 确保推荐结果来自多本书。

放置位置: backend/src/core/knowledge_qa/neo4j/diversity_rerank.py
"""

from __future__ import annotations

from collections import defaultdict


def diversity_rerank(
    items: list[dict],
    max_per_book: int = 3,
    book_key: str = "book_id",
) -> list[dict]:
    """按书籍来源分组重排，避免单一来源垄断推荐结果。

    策略: 每本书最多取 max_per_book 项，各书交替排列。
    结果中不会出现连续 2 条来自同一本书的情况。

    Args:
        items: 待排序的项目列表，每项需有 book_key 字段
        max_per_book: 每本书最多保留条数
        book_key: 书籍标识的字段名

    Returns:
        重排后的列表

    Examples:
        >>> items = [
        ...     {"name": "A1", "book_id": "B1"},
        ...     {"name": "A2", "book_id": "B1"},
        ...     {"name": "A3", "book_id": "B1"},
        ...     {"name": "B1", "book_id": "B2"},
        ...     {"name": "B2", "book_id": "B2"},
        ... ]
        >>> result = diversity_rerank(items, max_per_book=2)
        >>> [r["book_id"] for r in result]
        ['B1', 'B2', 'B1', 'B2']
    """
    by_book: dict[str, list[dict]] = defaultdict(list)
    for item in items:
        by_book[item.get(book_key, "unknown")].append(item)

    result = []
    round_idx = 0
    book_order = sorted(by_book.keys())

    while any(by_book[bid] for bid in book_order):
        for book_id in book_order:
            if by_book[book_id] and round_idx < max_per_book:
                result.append(by_book[book_id].pop(0))
        round_idx += 1

    return result


def compute_convergence_score(items: list[dict], book_key: str = "book_id") -> float:
    """计算收敛分数 — 衡量推荐结果的来源多样性。

    Returns:
        0.0 (全部来自同一本书) ~ 1.0 (完美均匀分布)
    """
    if not items:
        return 0.0

    book_counts: dict[str, int] = defaultdict(int)
    for item in items:
        book_counts[item.get(book_key, "unknown")] += 1

    if len(book_counts) <= 1:
        return 0.0

    n = len(items)
    k = len(book_counts)
    ideal_per_book = n / k

    deviation = sum(abs(count - ideal_per_book) for count in book_counts.values())
    max_deviation = n * (k - 1) / k  # 最大可能偏差

    if max_deviation == 0:
        return 1.0

    return 1.0 - (deviation / (2 * max_deviation))
