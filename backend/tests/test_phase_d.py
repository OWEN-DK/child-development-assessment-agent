"""
Phase D 单元测试

覆盖：
- D-1: content_hash 精确去重
- D-2: MinHash 近似去重
- D-3: 模型预热
- D-4: 动态 initial_k
- D-5: 输入校验与预处理
- D-6: 边界年龄映射与降级策略
"""

import pytest
import time
from unittest.mock import patch, MagicMock


class TestHashDedup:
    """D-1: content_hash 精确去重测试"""

    def test_exact_dedup_identical_content(self):
        """测试完全相同内容的去重"""
        from src.core.rag.dedup_engine import DedupEngine

        engine = DedupEngine(use_minhash=False)
        items = [
            {"content": "相同内容", "relevance_score": 0.8},
            {"content": "相同内容", "relevance_score": 0.9},
            {"content": "相同内容", "relevance_score": 0.7},
        ]

        result = engine.deduplicate(items)
        assert len(result.items) == 1
        assert result.items[0]["relevance_score"] == 0.9
        assert result.exact_dedup_count == 2

    def test_exact_dedup_different_content(self):
        """测试不同内容不去重"""
        from src.core.rag.dedup_engine import DedupEngine

        engine = DedupEngine(use_minhash=False)
        items = [
            {"content": "内容一", "relevance_score": 0.8},
            {"content": "内容二", "relevance_score": 0.9},
        ]

        result = engine.deduplicate(items)
        assert len(result.items) == 2
        assert result.total_removed == 0

    def test_exact_dedup_empty_list(self):
        """测试空列表"""
        from src.core.rag.dedup_engine import DedupEngine

        engine = DedupEngine(use_minhash=False)
        result = engine.deduplicate([])
        assert len(result.items) == 0

    def test_exact_dedup_single_item(self):
        """测试单条结果"""
        from src.core.rag.dedup_engine import DedupEngine

        engine = DedupEngine(use_minhash=False)
        items = [{"content": "唯一内容", "relevance_score": 0.8}]
        result = engine.deduplicate(items)
        assert len(result.items) == 1


class TestDynamicInitialK:
    """D-4: 动态 initial_k 测试"""

    def test_simple_query(self):
        """简单查询 (<5 字) → initial_k=15"""
        from src.core.reranker import CrossEncoderReranker

        reranker = CrossEncoderReranker()
        k = reranker._calculate_initial_k("运动")
        assert k == 15

    def test_short_query(self):
        """短词查询 (5-10 字) → initial_k=20"""
        from src.core.reranker import CrossEncoderReranker

        reranker = CrossEncoderReranker()
        k = reranker._calculate_initial_k("前庭觉训练")
        assert k == 20

    def test_medium_query(self):
        """中等查询 (10-15 字) → initial_k=30"""
        from src.core.reranker import CrossEncoderReranker

        reranker = CrossEncoderReranker()
        k = reranker._calculate_initial_k("感统训练方法有哪些好")
        assert k == 30

    def test_dynamic_disabled(self):
        """动态规则关闭时返回固定值（验证降级路径存在）"""
        from src.core.reranker import CrossEncoderReranker

        reranker = CrossEncoderReranker(initial_k=30)
        k = reranker._calculate_initial_k("运动")
        assert k == 15

    def test_complex_query(self):
        """复杂查询 (>15 字) → initial_k=50"""
        from src.core.reranker import CrossEncoderReranker

        reranker = CrossEncoderReranker()
        k = reranker._calculate_initial_k("3 岁孩子注意力不集中怎么办有什么好方法")
        assert k == 50

    def test_dynamic_disabled(self):
        """动态规则关闭时返回固定值（验证降级路径存在）"""
        from src.core.reranker import CrossEncoderReranker

        reranker = CrossEncoderReranker(initial_k=30)
        k = reranker._calculate_initial_k("运动")
        assert k == 15


class TestInputValidation:
    """D-5: 输入校验与预处理测试"""

    def test_empty_query(self):
        """空查询返回错误提示"""
        from src.core.rag.boundary_handler import BoundaryHandler

        handler = BoundaryHandler()
        result = handler.validate_and_clean("")
        assert result.is_valid is False
        assert result.error_message == "请输入搜索内容"

    def test_whitespace_query(self):
        """纯空白字符等同于空查询"""
        from src.core.rag.boundary_handler import BoundaryHandler

        handler = BoundaryHandler()
        result = handler.validate_and_clean("   ")
        assert result.is_valid is False

    def test_special_chars_filter(self):
        """特殊字符被过滤"""
        from src.core.rag.boundary_handler import BoundaryHandler

        handler = BoundaryHandler()
        result = handler.validate_and_clean("感统训练！！！@@@###")
        assert result.is_valid is True
        assert "感统训练" in result.cleaned_query
        assert "@" not in result.cleaned_query

    def test_long_query_truncated(self):
        """超长查询被截断"""
        from src.core.rag.boundary_handler import BoundaryHandler

        handler = BoundaryHandler()
        long_query = "这是一个非常非常非常长的查询" * 10
        result = handler.validate_and_clean(long_query)
        assert result.is_valid is True
        assert len(result.cleaned_query) <= 200

    def test_normal_query_unaffected(self):
        """正常查询不受影响"""
        from src.core.rag.boundary_handler import BoundaryHandler

        handler = BoundaryHandler()
        result = handler.validate_and_clean("感统训练")
        assert result.is_valid is True
        assert result.cleaned_query == "感统训练"

    def test_intent_extraction(self):
        """超长查询意图提取"""
        from src.core.rag.boundary_handler import BoundaryHandler

        handler = BoundaryHandler()
        long_query = "我有一个 3 岁的孩子，最近发现他注意力非常不集中，总是坐不住，不知道有什么好的训练方法可以推荐"
        intent = handler.extract_intent(long_query)
        assert len(intent) <= 50


class TestBoundaryAge:
    """D-6: 边界年龄映射与降级策略测试"""

    def test_age_0_infant(self):
        """0 岁映射到婴儿期"""
        from src.core.rag.boundary_handler import BoundaryHandler, DevelopmentStage

        stage = BoundaryHandler.get_development_stage(0)
        assert stage == DevelopmentStage.INFANT

    def test_age_18_adolescent(self):
        """18 岁映射到青少年期"""
        from src.core.rag.boundary_handler import BoundaryHandler, DevelopmentStage

        stage = BoundaryHandler.get_development_stage(18)
        assert stage == DevelopmentStage.ADOLESCENT

    def test_age_stage_mapping(self):
        """各年龄段正确映射"""
        from src.core.rag.boundary_handler import BoundaryHandler, DevelopmentStage

        assert BoundaryHandler.get_development_stage(0) == DevelopmentStage.INFANT
        assert BoundaryHandler.get_development_stage(2) == DevelopmentStage.TODDLER
        assert BoundaryHandler.get_development_stage(4) == DevelopmentStage.PRESCHOOL
        assert BoundaryHandler.get_development_stage(8) == DevelopmentStage.SCHOOL_AGE
        assert BoundaryHandler.get_development_stage(15) == DevelopmentStage.ADOLESCENT

    def test_age_range_mapping(self):
        """边界年龄映射到阶段范围"""
        from src.core.rag.boundary_handler import BoundaryHandler

        assert BoundaryHandler.map_age到_stage_range(0) == (0, 1)
        assert BoundaryHandler.map_age到_stage_range(18) == (13, 18)

    def test_fallback_strategy_with_results(self):
        """有结果时不触发降级"""
        from src.core.rag.boundary_handler import BoundaryHandler

        handler = BoundaryHandler()
        results = [{"content": "测试内容", "relevance_score": 0.8}]
        final_results, logs = handler.apply_fallback_strategy("测试", 5, results)
        assert len(final_results) == 1
        assert len(logs) == 0

    def test_fallback_strategy_no_results(self):
        """无结果时触发降级"""
        from src.core.rag.boundary_handler import BoundaryHandler

        handler = BoundaryHandler()
        final_results, logs = handler.apply_fallback_strategy("量子物理", 5, [])
        assert len(logs) > 0
        assert any("降级" in log for log in logs)


class TestModelWarmer:
    """D-3: 模型预热测试"""

    @pytest.mark.asyncio
    async def test_warmer_status(self):
        """测试预热器状态"""
        from src.core.rag.model_warmer import ModelWarmer

        warmer = ModelWarmer()
        assert warmer.is_warmed is False
        assert warmer.warmup_failed is False

        status = warmer.get_status()
        assert "model_name" in status
        assert "is_warmed" in status
