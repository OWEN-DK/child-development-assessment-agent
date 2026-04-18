"""权重决策逻辑单元测试"""

import pytest
from src.core.hybrid_retrieval import HybridRetrievalMerger
from src.core.rag.query_analyzer import QueryAnalyzer
from src.config import settings


class TestWeightDecision:
    """动态权重决策测试"""

    def setup_method(self):
        """每个测试前初始化分析器"""
        self.analyzer = QueryAnalyzer()

    def test_short_query_weights(self):
        """测试短查询权重 - BM25=0.3, Vector=0.7"""
        bm25_w, vector_w = HybridRetrievalMerger.get_dynamic_weights(
            "运动", query_analyzer=self.analyzer
        )
        assert bm25_w == pytest.approx(0.3, abs=0.01)
        assert vector_w == pytest.approx(0.7, abs=0.01)

    def test_terminology_weights(self):
        """测试专业术语权重 - BM25=0.7, Vector=0.3"""
        bm25_w, vector_w = HybridRetrievalMerger.get_dynamic_weights(
            "感统训练", query_analyzer=self.analyzer
        )
        assert bm25_w == pytest.approx(0.7, abs=0.01)
        assert vector_w == pytest.approx(0.3, abs=0.01)

    def test_descriptive_weights(self):
        """测试描述性查询权重 - BM25=0.4, Vector=0.6"""
        bm25_w, vector_w = HybridRetrievalMerger.get_dynamic_weights(
            "3 岁儿童语言发展迟缓怎么办", query_analyzer=self.analyzer
        )
        assert bm25_w == pytest.approx(0.4, abs=0.01)
        assert vector_w == pytest.approx(0.6, abs=0.01)

    def test_complex_weights(self):
        """测试复杂查询权重 - BM25=0.5, Vector=0.5"""
        bm25_w, vector_w = HybridRetrievalMerger.get_dynamic_weights(
            "前庭觉训练和精细动作训练有什么区别", query_analyzer=self.analyzer
        )
        assert bm25_w == pytest.approx(0.5, abs=0.01)
        assert vector_w == pytest.approx(0.5, abs=0.01)

    def test_fixed_weight_fallback(self):
        """测试固定权重回滚"""
        bm25_w, vector_w = HybridRetrievalMerger.get_dynamic_weights(
            "运动",
            query_analyzer=self.analyzer,
            strategy="fixed",
        )
        assert bm25_w == pytest.approx(settings.rag_hybrid_bm25_weight, abs=0.01)
        assert vector_w == pytest.approx(1 - settings.rag_hybrid_bm25_weight, abs=0.01)

    def test_age_micro_adjustment(self):
        """测试年龄微调 - 低龄用户 BM25 权重降低"""
        # 2 岁用户，短查询
        bm25_w, vector_w = HybridRetrievalMerger.get_dynamic_weights(
            "运动", age=2, query_analyzer=self.analyzer
        )
        # BM25 权重应从 0.3 降至 0.3*0.95=0.285
        assert bm25_w == pytest.approx(0.285, abs=0.01)

        # 验证不低于下限
        bm25_w, vector_w = HybridRetrievalMerger.get_dynamic_weights(
            "运动", age=1, query_analyzer=self.analyzer
        )
        assert bm25_w >= 0.2

    def test_custom_weight_config(self):
        """测试自定义权重配置"""
        custom_config = {
            "short": {"bm25": 0.2, "vector": 0.8},
            "default": {"bm25": 0.5, "vector": 0.5},
        }
        bm25_w, vector_w = HybridRetrievalMerger.get_dynamic_weights(
            "运动",
            query_analyzer=self.analyzer,
            weight_config=custom_config,
        )
        assert bm25_w == pytest.approx(0.2, abs=0.01)
        assert vector_w == pytest.approx(0.8, abs=0.01)

    def test_default_query_type_weights(self):
        """测试默认查询类型权重"""
        bm25_w, vector_w = HybridRetrievalMerger.get_dynamic_weights(
            "儿童训练方法", query_analyzer=self.analyzer
        )
        assert bm25_w == pytest.approx(0.5, abs=0.01)
        assert vector_w == pytest.approx(0.5, abs=0.01)

    def test_weights_sum_to_one(self):
        """测试权重之和为 1"""
        test_queries = [
            "运动",
            "感统训练",
            "3 岁儿童语言发展迟缓怎么办",
            "前庭觉训练和精细动作训练有什么区别",
            "儿童训练方法",
        ]
        for query in test_queries:
            bm25_w, vector_w = HybridRetrievalMerger.get_dynamic_weights(
                query, query_analyzer=self.analyzer
            )
            assert (bm25_w + vector_w) == pytest.approx(1.0, abs=0.01), (
                f"Failed for query: {query}"
            )
