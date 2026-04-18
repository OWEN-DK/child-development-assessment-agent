import pytest


def test_calculate_mrr():
    """MRR = 平均倒数排名，Q为测试用例总数，rank_i为第i个用例第一个相关结果的排名"""
    from src.core.rag.metrics_calculator import calculate_mrr

    # 第一个结果就是相关的
    assert calculate_mrr(["doc1"], ["doc1", "doc2", "doc3"]) == 1.0
    # 第二个结果是相关的
    assert calculate_mrr(["doc2"], ["doc1", "doc2", "doc3"]) == 0.5
    # 第三个结果是相关的
    assert calculate_mrr(["doc3"], ["doc1", "doc2", "doc3"]) == 1 / 3
    # 没有相关结果
    assert calculate_mrr(["doc4"], ["doc1", "doc2", "doc3"]) == 0.0


def test_calculate_ndcg():
    """NDCG@k = DCG@k / IDCG@k，DCG = sum(rel_i / log2(i+1))"""
    from src.core.rag.metrics_calculator import calculate_ndcg

    # 完全匹配
    assert calculate_ndcg(["doc1", "doc2"], ["doc1", "doc2", "doc3"], k=3) == 1.0
    # 部分匹配
    assert calculate_ndcg(
        ["doc1", "doc2"], ["doc2", "doc1", "doc3"], k=3
    ) == pytest.approx(1.0)
    # 无相关结果 → 返回 0.0
    assert calculate_ndcg(["doc4"], ["doc1", "doc2", "doc3"], k=3) == 0.0
    # 空期望文档 → 返回 None
    assert calculate_ndcg([], ["doc1", "doc2"], k=3) is None


def test_calculate_precision_recall():
    """Precision = TP/(TP+FP), Recall = TP/(TP+FN)"""
    from src.core.rag.metrics_calculator import calculate_precision, calculate_recall

    # 完全匹配
    assert calculate_precision(["doc1", "doc2"], ["doc1", "doc2"]) == 1.0
    assert calculate_recall(["doc1", "doc2"], ["doc1", "doc2"]) == 1.0
    # 部分匹配：检索3个，2个相关；期望2个，命中2个
    assert calculate_precision(["doc1", "doc2"], ["doc1", "doc2", "doc3"]) == 2 / 3
    assert calculate_recall(["doc1", "doc2"], ["doc1", "doc2", "doc3"]) == 1.0
    # 部分匹配：检索2个，1个相关；期望2个，命中1个
    assert calculate_precision(["doc1", "doc2"], ["doc1", "doc3"]) == 0.5
    assert calculate_recall(["doc1", "doc2"], ["doc1", "doc3"]) == 0.5
    # 无相关结果
    assert calculate_precision(["doc1"], ["doc2", "doc3"]) == 0.0
    assert calculate_recall(["doc1"], ["doc2", "doc3"]) == 0.0
    # 空期望文档
    assert calculate_precision([], ["doc1", "doc2"]) == 0.0
    assert calculate_recall([], ["doc1", "doc2"]) == 0.0


def test_calculate_hit_rate():
    """测试命中率计算"""
    from src.core.rag.metrics_calculator import calculate_hit_rate

    # 命中1个，期望2个 → 0.5
    assert calculate_hit_rate(["doc1", "doc2"], ["doc1", "doc3"], k=2) == 0.5
    # 命中全部
    assert calculate_hit_rate(["doc1", "doc2"], ["doc1", "doc2", "doc3"], k=3) == 1.0
    # 命中0个
    assert calculate_hit_rate(["doc1", "doc2"], ["doc3", "doc4"], k=2) == 0.0
    # 空期望
    assert calculate_hit_rate([], ["doc1", "doc2"], k=2) == 0.0
