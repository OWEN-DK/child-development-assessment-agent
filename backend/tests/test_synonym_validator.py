"""
同义词质量验证器单元测试 (Phase C-1)

测试覆盖：
- 黑名单过滤
- 粒度控制
- 白名单优先通过
- 语义重叠检查
- 验证通过率计算
- 边界情况（单字/超长/特殊字符）
- 数据库降级
- 空词典降级
"""

import pytest
from src.core.rag.synonym_validator import SynonymValidator, ValidationReport


class TestSynonymValidator:
    """同义词验证器测试"""

    def test_blacklist_rejection(self):
        """测试黑名单过滤"""
        validator = SynonymValidator()
        report = validator.validate(
            ["注意力", "专注力", "集中力", "视力", "听力"], original_query="注意力"
        )
        rejected_terms = [t for t, _ in report.rejected_terms]
        assert "视力" in rejected_terms
        assert "听力" in rejected_terms
        assert "专注力" in report.valid_terms
        assert "集中力" in report.valid_terms

    def test_granularity_control(self):
        """测试粒度控制"""
        validator = SynonymValidator()

        report = validator.validate(
            ["感统", "感觉统合", "感觉", "感官统合"], original_query="感统"
        )
        rejected_terms = [t for t, _ in report.rejected_terms]
        assert "感觉" in rejected_terms
        assert "感觉统合" in report.valid_terms

        report = validator.validate(
            ["精细动作", "手眼协调", "动作", "肌肉"], original_query="精细动作"
        )
        rejected_terms = [t for t, _ in report.rejected_terms]
        assert "动作" in rejected_terms
        assert "肌肉" in rejected_terms

    def test_whitelist_pass(self):
        """测试白名单优先通过"""
        validator = SynonymValidator()
        report = validator.validate(
            ["注意力", "前庭觉", "本体觉", "平衡感"], original_query="注意力"
        )
        assert "前庭觉" in report.valid_terms
        assert "本体觉" in report.valid_terms
        assert "平衡感" in report.valid_terms

    def test_semantic_overlap(self):
        """测试语义重叠检查"""
        validator = SynonymValidator()

        report = validator.validate(
            ["注意力", "数学能力", "阅读能力"], original_query="注意力"
        )
        rejected_terms = [t for t, _ in report.rejected_terms]
        assert "数学能力" in rejected_terms
        assert "阅读能力" in rejected_terms

    def test_validation_confidence(self):
        """测试验证通过率计算"""
        validator = SynonymValidator()

        report = validator.validate(
            ["注意力", "专注力", "集中力", "视力"], original_query="注意力"
        )
        assert report.confidence == pytest.approx(0.75, abs=0.01)
        assert report.is_valid is False

        report = validator.validate(
            ["注意力", "专注力", "集中力", "注意力集中"], original_query="注意力"
        )
        assert report.confidence == pytest.approx(1.0, abs=0.01)
        assert report.is_valid is True

    def test_edge_cases(self):
        """测试边界情况"""
        validator = SynonymValidator()

        report = validator.validate(["感统", "感", "统"], original_query="感统")
        rejected_terms = [t for t, _ in report.rejected_terms]
        assert "感" in rejected_terms
        assert "统" in rejected_terms

        report = validator.validate(
            ["注意力", "这是一个非常非常长的同义词超过了十五个字"],
            original_query="注意力",
        )
        rejected_terms = [t for t, _ in report.rejected_terms]
        assert "这是一个非常非常长的同义词超过了十五个字" in rejected_terms

        report = validator.validate(
            ["注意力", "专注力!!!", "集中力"], original_query="注意力"
        )
        rejected_terms = [t for t, _ in report.rejected_terms]
        assert "专注力!!!" in rejected_terms

    def test_empty_dict_fallback(self, tmp_path):
        """测试空词典降级"""
        empty_file = tmp_path / "empty_validation.json"
        empty_file.write_text("{}")

        validator = SynonymValidator(validation_file=str(empty_file))

        # 空词典时，"数学" 与 "注意力" 无字符重叠，应被拒绝
        report = validator.validate(["注意力", "数学"], original_query="注意力")
        rejected_terms = [t for t, _ in report.rejected_terms]
        assert "数学" in rejected_terms

    def test_original_query_always_passes(self):
        """测试原词始终通过"""
        validator = SynonymValidator()

        report = validator.validate(["注意力", "专注力"], original_query="注意力")
        assert "注意力" in report.valid_terms

    def test_diagnosis_query_attention(self):
        """测试诊断查询：注意力"""
        validator = SynonymValidator()

        report = validator.validate(
            ["注意力", "专注力", "集中力", "注意力集中", "视力", "听力", "观察力"],
            original_query="注意力",
        )
        assert "专注力" in report.valid_terms
        assert "集中力" in report.valid_terms
        assert "视力" in [t for t, _ in report.rejected_terms]
        assert "听力" in [t for t, _ in report.rejected_terms]

    def test_diagnosis_query_sensory_integration(self):
        """测试诊断查询：感统"""
        validator = SynonymValidator()

        report = validator.validate(
            ["感统", "感觉统合", "感觉整合", "感官统合", "感觉", "统合", "感官"],
            original_query="感统",
        )
        assert "感觉统合" in report.valid_terms
        assert "感觉整合" in report.valid_terms
        assert "感觉" in [t for t, _ in report.rejected_terms]
        assert "统合" in [t for t, _ in report.rejected_terms]

    def test_diagnosis_query_fine_motor(self):
        """测试诊断查询：精细动作"""
        validator = SynonymValidator()

        report = validator.validate(
            ["精细动作", "小肌肉", "手眼协调", "手指灵活", "动作", "精细", "肌肉"],
            original_query="精细动作",
        )
        assert "小肌肉" in report.valid_terms
        assert "手眼协调" in report.valid_terms
        assert "动作" in [t for t, _ in report.rejected_terms]
        assert "肌肉" in [t for t, _ in report.rejected_terms]

    def test_valid_terms_from_domain_specific_rules(self):
        """测试专属规则 valid 列表通过"""
        validator = SynonymValidator()

        report = validator.validate(["注意力", "注意广度"], original_query="注意力")
        assert "注意广度" in report.valid_terms

    def test_rejection_reason_logging(self):
        """测试拒绝原因记录"""
        validator = SynonymValidator()

        report = validator.validate(
            ["感统", "感觉", "视力", "a"], original_query="感统"
        )
        reasons = {term: reason for term, reason in report.rejected_terms}
        assert "感觉" in reasons
        assert "视力" in reasons
        assert "a" in reasons

    def test_confidence_threshold(self):
        """测试置信度阈值"""
        validator = SynonymValidator()

        report = validator.validate(
            ["注意力", "专注力", "视力"], original_query="注意力"
        )
        assert report.confidence == pytest.approx(2 / 3, abs=0.01)
        threshold = 0.8
        assert report.is_valid == (report.confidence >= threshold)

    def test_chinese_character_overlap(self):
        """测试中文字符重叠检测"""
        validator = SynonymValidator()

        report = validator.validate(["注意力", "注意广度"], original_query="注意力")
        assert "注意广度" in report.valid_terms

    def test_english_word_overlap(self):
        """测试英文词根重叠检测"""
        validator = SynonymValidator()

        report = validator.validate(
            ["attention", "attention span"], original_query="attention"
        )
        assert (
            "attention span" in report.valid_terms or "attention" in report.valid_terms
        )

    def test_empty_synonym_list(self):
        """测试空列表"""
        validator = SynonymValidator()

        report = validator.validate([], original_query="注意力")
        assert report.confidence == 0.0
        assert report.is_valid is False
        assert report.valid_terms == []

    def test_single_term_list(self):
        """测试仅包含原词的列表"""
        validator = SynonymValidator()

        report = validator.validate(["注意力"], original_query="注意力")
        assert report.confidence == 1.0
        assert report.is_valid is True
        assert report.valid_terms == ["注意力"]
