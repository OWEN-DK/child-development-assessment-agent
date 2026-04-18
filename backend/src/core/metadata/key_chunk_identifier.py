"""关键块识别模块

识别章节开头、内容突变处等关键分块。
"""

from typing import List, Set

from llama_index.core.schema import Node


def identify_key_chunks(nodes: List[Node], max_key_chunks: int = 50) -> Set[int]:
    """识别关键分块（章节开头、内容突变处）

    策略：
    1. 每个章节的前 2 个分块
    2. 内容长度突变处（可能是新主题）
    3. 均匀采样：每隔 N 个分块取一个

    Args:
        nodes: 分块列表
        max_key_chunks: 最大关键分块数

    Returns:
        关键分块的索引集合
    """
    key_indices: Set[int] = set()
    n = len(nodes)

    if n == 0:
        return key_indices

    current_chapter = None
    for idx, node in enumerate(nodes):
        chapter = node.metadata.get("chapter_title") or node.metadata.get("chapter")
        if chapter != current_chapter:
            key_indices.add(idx)
            if idx + 1 < n:
                key_indices.add(idx + 1)
            current_chapter = chapter

    if len(key_indices) < max_key_chunks:
        step = max(1, n // max_key_chunks)
        for idx in range(0, n, step):
            key_indices.add(idx)
            if len(key_indices) >= max_key_chunks:
                break

    if n > 10:
        lengths = [len(node.get_content()) for node in nodes]
        avg_length = sum(lengths) / len(lengths)
        for idx in range(1, min(100, n)):
            if lengths[idx] > avg_length * 1.5 or lengths[idx] < avg_length * 0.5:
                key_indices.add(idx)

    if len(key_indices) > max_key_chunks:
        key_indices = set(sorted(key_indices)[:max_key_chunks])

    return key_indices
