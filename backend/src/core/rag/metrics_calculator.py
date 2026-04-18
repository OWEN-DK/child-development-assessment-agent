import math
from typing import List, Optional


def calculate_mrr(relevant_docs: List[str], retrieved_docs: List[str]) -> float:
    """计算平均倒数排名(MRR)

    MRR = 1/rank，rank为第一个相关结果的排名（从1开始）
    """
    for idx, doc_id in enumerate(retrieved_docs):
        if doc_id in relevant_docs:
            return 1.0 / (idx + 1)
    return 0.0


def calculate_dcg(
    relevant_docs: List[str], retrieved_docs: List[str], k: int = 10
) -> float:
    """计算折损累计增益(DCG)

    DCG = sum(rel_i / log2(i+1))，i从1开始
    """
    dcg = 0.0
    for idx, doc_id in enumerate(retrieved_docs[:k]):
        if doc_id in relevant_docs:
            dcg += 1.0 / math.log2(idx + 2)
    return dcg


def calculate_idcg(relevant_docs: List[str], k: int = 10) -> float:
    """计算理想折损累计增益(IDCG)"""
    idcg = 0.0
    for idx in range(min(len(relevant_docs), k)):
        idcg += 1.0 / math.log2(idx + 2)
    return idcg


def calculate_ndcg(
    relevant_docs: List[str], retrieved_docs: List[str], k: int = 10
) -> Optional[float]:
    """计算归一化折损累计增益(NDCG)

    NDCG@k = DCG@k / IDCG@k

    Returns:
        float: NDCG 值 [0, 1]
        None: 当 relevant_docs 为空或 IDCG 为 0 时（应跳过聚合，避免拉低平均分）
    """
    if not relevant_docs:
        return None

    dcg = calculate_dcg(relevant_docs, retrieved_docs, k)
    idcg = calculate_idcg(relevant_docs, k)

    if idcg == 0:
        return None

    return dcg / idcg


def calculate_hit_rate(
    relevant_docs: List[str], retrieved_docs: List[str], k: int = 10
) -> float:
    """计算召回率@k（命中的相关文档数/总相关文档数）
    若需要标准行业hit rate定义（是否至少命中1个，返回0或1），使用：
    return 1.0 if len(set(retrieved_docs[:k]) & set(relevant_docs)) > 0 else 0.0
    """
    if not relevant_docs:
        return 0.0

    hits = len(set(retrieved_docs[:k]) & set(relevant_docs))
    return hits / len(relevant_docs)


def calculate_precision(
    relevant_docs: List[str], retrieved_docs: List[str], k: int = 10
) -> float:
    """计算精确率@k（Precision@k）

    Precision = 命中数 / 检索结果数
    衡量检索结果的准确性
    """
    retrieved_at_k = retrieved_docs[:k]
    if not retrieved_at_k:
        return 0.0

    hits = len(set(retrieved_at_k) & set(relevant_docs))
    return hits / len(retrieved_at_k)


def calculate_recall(
    relevant_docs: List[str], retrieved_docs: List[str], k: int = 10
) -> float:
    """计算召回率@k（Recall@k）

    Recall = 命中数 / 期望相关文档数
    衡量检索结果的覆盖度
    """
    if not relevant_docs:
        return 0.0

    retrieved_at_k = retrieved_docs[:k]
    hits = len(set(retrieved_at_k) & set(relevant_docs))
    return hits / len(relevant_docs)
