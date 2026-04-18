"""测试 MinHash + LSH 去重器"""

import pytest
from src.service.rag_test_case_service import DraftDeduplicator


class TestDraftDeduplicator:
    """测试 DraftDeduplicator 类"""

    def test_init_default_params(self):
        """测试默认参数初始化"""
        dedup = DraftDeduplicator()
        assert dedup.threshold == 0.8
        assert dedup.num_perm == 128

    def test_init_custom_params(self):
        """测试自定义参数初始化"""
        dedup = DraftDeduplicator(threshold=0.7, num_perm=256)
        assert dedup.threshold == 0.7
        assert dedup.num_perm == 256

    def test_identical_queries_are_duplicates(self):
        """测试完全相同的查询被识别为重复"""
        dedup = DraftDeduplicator(threshold=0.8)
        dedup.add_existing("1岁宝宝走路正常吗")
        assert dedup.is_duplicate("1岁宝宝走路正常吗") is True

    def test_similar_queries_are_duplicates(self):
        """测试高度相似的查询被识别为重复"""
        dedup = DraftDeduplicator(threshold=0.5)
        dedup.add_existing("宝宝什么时候会走路")
        # 相似度高（共享关键词：宝宝、会、走路）
        assert dedup.is_duplicate("宝宝什么时候会走路呢") is True

    def test_different_queries_not_duplicates(self):
        """测试不同的查询不被识别为重复"""
        dedup = DraftDeduplicator(threshold=0.8)
        dedup.add_existing("宝宝什么时候会走路")
        # 完全不同主题
        assert dedup.is_duplicate("如何培养孩子的阅读习惯") is False

    def test_add_multiple_existing(self):
        """测试添加多个已有查询"""
        dedup = DraftDeduplicator(threshold=0.5)
        dedup.add_existing("宝宝走路正常吗")
        dedup.add_existing("宝宝说话正常吗")
        dedup.add_existing("宝宝吃饭正常吗")

        # 应该能正确识别重复（共享关键词：宝宝、正常吗）
        assert dedup.is_duplicate("宝宝走路正常吗") is True
        assert dedup.is_duplicate("宝宝说话正常吗") is True
        assert dedup.is_duplicate("宝宝吃饭正常吗") is True

    def test_empty_query(self):
        """测试空查询处理"""
        dedup = DraftDeduplicator()
        dedup.add_existing("测试查询")
        # 空查询不应该被识别为重复
        assert dedup.is_duplicate("") is False

    def test_threshold_sensitivity(self):
        """测试阈值敏感性"""
        # 低阈值：更容易判定为重复
        dedup_low = DraftDeduplicator(threshold=0.2)
        dedup_low.add_existing("宝宝什么时候开始学会走路正常")
        # 共享部分关键词（宝宝、走路、正常）
        assert dedup_low.is_duplicate("宝宝几个月学会走路算正常") is True

        # 高阈值：更难判定为重复
        dedup_high = DraftDeduplicator(threshold=0.9)
        dedup_high.add_existing("宝宝什么时候开始学会走路正常")
        # 用词差异大
        assert dedup_high.is_duplicate("婴儿行走几个月") is False

    def test_large_scale_performance(self):
        """测试大规模数据性能"""
        import time

        dedup = DraftDeduplicator(threshold=0.7)

        # 添加 1000 条已有查询
        for i in range(1000):
            dedup.add_existing(f"测试查询{i}")

        # 测量查询性能
        start = time.time()
        for i in range(100):
            dedup.is_duplicate(f"新查询{i}")
        elapsed = time.time() - start

        # 100 次查询应该在 1 秒内完成
        assert elapsed < 1.0, f"查询耗时 {elapsed:.3f}s 超过 1s"

    def test_chinese_text_segmentation(self):
        """测试中文分词效果"""
        dedup = DraftDeduplicator(threshold=0.4)

        # 相同表述
        dedup.add_existing("儿童语言发育迟缓怎么办")

        # 应该能识别相似性（共享关键词：语言、发育、迟缓）
        assert dedup.is_duplicate("儿童语言发育迟缓如何处理") is True

    def test_minhash_signature_consistency(self):
        """测试 MinHash 签名一致性"""
        dedup = DraftDeduplicator()

        # 相同查询应该产生相同的签名
        m1 = dedup._compute_minhash("测试查询")
        m2 = dedup._compute_minhash("测试查询")

        # Jaccard 相似度应该为 1.0
        similarity = m1.jaccard(m2)
        assert similarity == 1.0
