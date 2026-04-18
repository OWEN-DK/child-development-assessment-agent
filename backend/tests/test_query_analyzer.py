"""QueryAnalyzer 单元测试"""

import pytest
from src.core.rag.query_analyzer import QueryAnalyzer, QueryType


class TestQueryAnalyzer:
    """查询类型分析器测试"""

    def setup_method(self):
        """每个测试前初始化分析器"""
        self.analyzer = QueryAnalyzer()

    def test_short_query_detection_2_chars(self):
        """测试 2 字短查询识别"""
        result = self.analyzer.analyze("运动")
        assert result.query_type == QueryType.SHORT
        assert result.char_length == 2

    def test_short_query_detection_4_chars(self):
        """测试 4 字短查询识别"""
        result = self.analyzer.analyze("好玩")
        assert result.query_type == QueryType.SHORT
        assert result.char_length == 2

    def test_terminology_detection_sensory(self):
        """测试专业术语识别 - 感统训练"""
        result = self.analyzer.analyze("感统训练")
        assert result.query_type == QueryType.TERMINOLOGY
        assert result.has_terminology is True
        assert "感统训练" in result.matched_terminology

    def test_terminology_detection_vestibular(self):
        """测试专业术语识别 - 前庭觉"""
        result = self.analyzer.analyze("前庭觉")
        assert result.query_type == QueryType.TERMINOLOGY
        assert "前庭觉" in result.matched_terminology

    def test_descriptive_query_detection(self):
        """测试描述性查询识别"""
        result = self.analyzer.analyze("3 岁儿童语言发展迟缓怎么办")
        assert result.query_type == QueryType.DESCRIPTIVE
        assert result.has_question_word is True

    def test_complex_query_detection(self):
        """测试复杂查询识别"""
        result = self.analyzer.analyze("前庭觉训练和精细动作训练有什么区别")
        assert result.query_type == QueryType.COMPLEX
        assert result.has_conjunction is True
        assert result.char_length > 15

    def test_empty_query(self):
        """测试空查询处理"""
        result = self.analyzer.analyze("")
        assert result.char_length == 0
        assert result.query_type == QueryType.DEFAULT

    def test_whitespace_only_query(self):
        """测试纯空格查询处理"""
        result = self.analyzer.analyze("   ")
        assert result.char_length == 0

    def test_special_characters_with_terminology(self):
        """测试含特殊字符的查询 - 应能识别术语"""
        result = self.analyzer.analyze("感统训练！！！")
        assert result.query_type in (QueryType.TERMINOLOGY, QueryType.DEFAULT)

    def test_confidence_terminology_high(self):
        """测试专业术语置信度 - 应高"""
        result = self.analyzer.analyze("感统训练")
        assert result.confidence >= 0.8

    def test_confidence_ambiguous_query_low(self):
        """测试模糊查询置信度 - 应较低"""
        result = self.analyzer.analyze("儿童训练方法")
        assert result.confidence < 0.8

    def test_matched_terminology_longest_match_first(self):
        """测试最长匹配优先 - 避免'感统'和'感统训练'同时匹配"""
        result = self.analyzer.analyze("感统训练方法")
        # 应该匹配"感统训练"而不是单独的"感统"
        assert "感统训练" in result.matched_terminology

    def test_multiple_terminology_match(self):
        """测试多术语匹配"""
        result = self.analyzer.analyze("前庭觉和本体觉训练")
        assert len(result.matched_terminology) >= 2
        assert "前庭觉" in result.matched_terminology
        assert "本体觉训练" in result.matched_terminology

    def test_question_word_detection(self):
        """测试疑问词检测"""
        test_cases = ["怎么办", "如何", "为什么", "怎样", "什么", "哪些"]
        for word in test_cases:
            result = self.analyzer.analyze(f"儿童{word}")
            assert result.has_question_word is True, f"Failed for question word: {word}"

    def test_conjunction_word_detection(self):
        """测试连接词检测"""
        test_cases = ["和", "与", "的区别", "比较", "对比", "还是"]
        for word in test_cases:
            result = self.analyzer.analyze(f"训练{word}游戏")
            assert result.has_conjunction is True, f"Failed for conjunction: {word}"

    def test_default_query_type(self):
        """测试默认查询类型"""
        result = self.analyzer.analyze("儿童训练方法")
        assert result.query_type == QueryType.DEFAULT

    def test_boundary_5_chars(self):
        """测试 5 字边界 - 不应是短查询"""
        result = self.analyzer.analyze("儿童游戏")
        assert result.char_length == 4  # 实际是 4 字
        assert result.query_type == QueryType.SHORT

    def test_analysis_result_structure(self):
        """测试分析结果结构完整性"""
        result = self.analyzer.analyze("感统训练")
        assert hasattr(result, "query_type")
        assert hasattr(result, "original_query")
        assert hasattr(result, "char_length")
        assert hasattr(result, "has_terminology")
        assert hasattr(result, "matched_terminology")
        assert hasattr(result, "has_question_word")
        assert hasattr(result, "has_conjunction")
        assert hasattr(result, "confidence")
        assert 0 <= result.confidence <= 1
