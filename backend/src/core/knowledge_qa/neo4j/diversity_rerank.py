"""来源多样性重排 — 确保推荐结果来自多本书。"""

from __future__ import annotations

from collections import defaultdict


def diversity_rerank(
    items: list[dict],
    max_per_book: int = 3,
    book_key: str = "book_id",
) -> list[dict]:
    """按书籍来源分组重排，避免单一来源垄断推荐结果。

    策略: 每本书最多取 max_per_book 项，各书交替排列。

    Args:
        items: 待排序的项目列表，每项需有 book_key 字段
        max_per_book: 每本书最多保留条数
        book_key: 书籍标识的字段名

    Returns:
        重排后的列表
    """
    by_book: dict[str, list[dict]] = defaultdict(list)
    for item in items:
        by_book[item.get(book_key, "unknown")].append(item)

    # 限制每本书的数量
    for book_id in by_book:
        by_book[book_id] = by_book[book_id][:max_per_book]

    result = []
    book_order = sorted(by_book.keys())
    round_idx = 0

    while True:
        added = False
        for book_id in book_order:
            if round_idx < len(by_book[book_id]):
                result.append(by_book[book_id][round_idx])
                added = True
        if not added:
            break
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
    max_deviation = n * (k - 1) / k

    if max_deviation == 0:
        return 1.0

    return 1.0 - (deviation / (2 * max_deviation))
