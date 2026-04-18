"""
本地同义词扩展器单元测试 (Phase C-2)

测试覆盖：
- 精确匹配
- 子串匹配
- 分词匹配
- 兜底成功率验证（≥80%）
- 诊断查询验证
- 数据库降级
"""

import pytest
from src.core.rag.local_synonym_expander import LocalSynonymExpander


class TestLocalSynonymExpander:
    """本地同义词扩展器测试"""

    def test_exact_match_attention(self):
        """测试精确匹配：注意力"""
        expander = LocalSynonymExpander()

        synonyms = expander.expand("注意力")
        assert "专注力" in synonyms
        assert "集中力" in synonyms
        assert "注意力" in synonyms

    def test_exact_match_sensory_integration(self):
        """测试精确匹配：感统"""
        expander = LocalSynonymExpander()

        synonyms = expander.expand("感统")
        assert "感觉统合" in synonyms
        assert "感觉整合" in synonyms
        assert "感官统合" in synonyms

    def test_exact_match_fine_motor(self):
        """测试精确匹配：精细动作"""
        expander = LocalSynonymExpander()

        synonyms = expander.expand("精细动作")
        assert "手眼协调" in synonyms
        assert "精细运动" in synonyms
        assert "小肌肉" in synonyms
        assert "精细动作" in synonyms

    def test_substring_match(self):
        """测试子串匹配"""
        expander = LocalSynonymExpander()

        synonyms = expander.expand("精细动作训练方法")
        assert "手眼协调" in synonyms
        assert "精细运动" in synonyms

    def test_tokenized_match(self):
        """测试分词匹配"""
        expander = LocalSynonymExpander()

        synonyms = expander.expand("孩子注意力不集中怎么办")
        assert "专注力" in synonyms
        assert "集中力" in synonyms

    def test_fallback_success_rate(self):
        """验证本地兜底对常见查询的成功率 ≥80%"""
        expander = LocalSynonymExpander()

        test_queries = [
            "注意力",
            "感统",
            "精细动作",
            "大运动",
            "前庭觉",
            "本体觉",
            "触觉",
            "语言",
            "认知",
            "社交",
            "专注力",
            "情绪调节",
            "平衡能力",
            "手眼协调",
        ]

        success_count = 0
        for query in test_queries:
            synonyms = expander.expand(query)
            if len(synonyms) >= 2:
                success_count += 1

        rate = success_count / len(test_queries)
        assert rate >= 0.8, f"本地兜底成功率 {rate:.2%} < 80%"

    def test_diagnosis_query_attention(self):
        """验证诊断测试：注意力"""
        expander = LocalSynonymExpander()

        synonyms = expander.expand("注意力")
        assert "专注力" in synonyms
        assert "集中力" in synonyms
        assert "视力" not in synonyms
        assert "听力" not in synonyms

    def test_diagnosis_query_sensory_integration(self):
        """验证诊断测试：感统"""
        expander = LocalSynonymExpander()

        synonyms = expander.expand("感统")
        assert "感觉统合" in synonyms
        assert "感觉整合" in synonyms
        assert "感觉" not in synonyms
        assert "统合" not in synonyms

    def test_diagnosis_query_fine_motor(self):
        """验证诊断测试：精细动作"""
        expander = LocalSynonymExpander()

        synonyms = expander.expand("精细动作")
        assert "手眼协调" in synonyms
        assert "小肌肉" in synonyms
        assert "动作" not in synonyms
        assert "肌肉" not in synonyms

    def test_original_term_always_included(self):
        """测试原词始终包含在结果中"""
        expander = LocalSynonymExpander()

        synonyms = expander.expand("未知词汇")
        assert "未知词汇" in synonyms

    def test_empty_dict_fallback(self, tmp_path):
        """测试空词典降级"""
        empty_file = tmp_path / "empty_synonyms.json"
        empty_file.write_text("{}")

        expander = LocalSynonymExpander(synonyms_file=str(empty_file))
        synonyms = expander.expand("注意力")

        assert synonyms == ["注意力"]

    def test_deduplication(self):
        """测试去重"""
        expander = LocalSynonymExpander()

        synonyms = expander.expand("注意力")
        assert len(synonyms) == len(set(synonyms))

    def test_gross_motor(self):
        """测试大运动"""
        expander = LocalSynonymExpander()

        synonyms = expander.expand("大运动")
        assert "粗大动作" in synonyms
        assert "大肌肉运动" in synonyms

    def test_vestibular(self):
        """测试前庭觉"""
        expander = LocalSynonymExpander()

        synonyms = expander.expand("前庭觉")
        assert "前庭感" in synonyms
        assert "平衡觉" in synonyms

    def test_proprioception(self):
        """测试本体觉"""
        expander = LocalSynonymExpander()

        synonyms = expander.expand("本体觉")
        assert "本体感" in synonyms
        assert "本体感觉" in synonyms

    def test_tactile(self):
        """测试触觉"""
        expander = LocalSynonymExpander()

        synonyms = expander.expand("触觉")
        assert "触觉系统" in synonyms
        assert "触觉防御" in synonyms

    def test_language(self):
        """测试语言"""
        expander = LocalSynonymExpander()

        synonyms = expander.expand("语言")
        assert "语言能力" in synonyms
        assert "语言表达" in synonyms

    def test_cognitive(self):
        """测试认知"""
        expander = LocalSynonymExpander()

        synonyms = expander.expand("认知")
        assert "认知能力" in synonyms
        assert "认知发展" in synonyms

    def test_social(self):
        """测试社交"""
        expander = LocalSynonymExpander()

        synonyms = expander.expand("社交")
        assert "社交能力" in synonyms
        assert "人际交往" in synonyms

    def test_emotion(self):
        """测试情绪"""
        expander = LocalSynonymExpander()

        synonyms = expander.expand("情绪")
        assert "情绪管理" in synonyms
        assert "情绪调节" in synonyms

    def test_emotion_regulation(self):
        """测试情绪调节"""
        expander = LocalSynonymExpander()

        synonyms = expander.expand("情绪调节")
        assert "情绪管理" in synonyms
        assert "情绪控制" in synonyms

    def test_concentration(self):
        """测试专注力"""
        expander = LocalSynonymExpander()

        synonyms = expander.expand("专注力")
        assert "注意力" in synonyms
        assert "集中力" in synonyms

    def test_hand_eye_coordination(self):
        """测试手眼协调"""
        expander = LocalSynonymExpander()

        synonyms = expander.expand("手眼协调")
        assert "精细动作" in synonyms
        assert "手眼配合" in synonyms

    def test_balance_ability(self):
        """测试平衡能力"""
        expander = LocalSynonymExpander()

        synonyms = expander.expand("平衡能力")
        assert "平衡感" in synonyms
        assert "前庭觉" in synonyms
