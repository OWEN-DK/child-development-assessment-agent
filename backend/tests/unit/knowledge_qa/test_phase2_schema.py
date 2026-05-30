"""Phase 2 单元测试：Schema 加固 + IntensityLevel 枚举 + 模糊匹配"""

import pytest
from pydantic import ValidationError


# ==================== P2-1: S2/S3 structured_data 子模型 ====================


class TestSection2StructuredData:
    """Section2StructuredData (identify_problems 问题识别) 测试"""

    def test_valid_problems_list(self):
        from src.schemas.knowledge_qa import Section2StructuredData, ProblemItem

        data = Section2StructuredData(
            problems=[
                ProblemItem(description="注意力不集中", severity="高", category="注意力"),
                ProblemItem(description="睡眠不足", severity="中"),
            ]
        )
        assert len(data.problems) == 2
        assert data.problems[0].severity == "高"
        assert data.problems[1].category == ""

    def test_empty_problems_default(self):
        from src.schemas.knowledge_qa import Section2StructuredData

        data = Section2StructuredData()
        assert data.problems == []

    def test_invalid_severity_rejected(self):
        from src.schemas.knowledge_qa import ProblemItem

        with pytest.raises(ValidationError):
            ProblemItem(description="测试", severity="无效级别")

    def test_section2_response_structured_data_typed(self):
        from src.schemas.knowledge_qa import Section2Response, Section2StructuredData

        resp = Section2Response(
            content="## 问题分析",
            structured_data=Section2StructuredData(
                problems=[
                    {"description": "焦虑", "severity": "中", "category": "情绪"},
                ]
            ),
        )
        assert isinstance(resp.structured_data, Section2StructuredData)
        assert len(resp.structured_data.problems) == 1

    def test_section2_response_backward_compat_dict(self):
        """structured_data 接受 dict 输入，自动转为子模型"""
        from src.schemas.knowledge_qa import Section2Response, Section2StructuredData

        resp = Section2Response(
            content="## 问题分析",
            structured_data={
                "problems": [
                    {"description": "焦虑", "severity": "中", "category": "情绪"},
                ]
            },
        )
        assert isinstance(resp.structured_data, Section2StructuredData)


class TestSection3StructuredData:
    """Section3StructuredData (recommend_types 运动类型推荐) 测试"""

    def test_valid_exercise_types(self):
        from src.schemas.knowledge_qa import Section3StructuredData, ExerciseTypeItem

        data = Section3StructuredData(
            exercise_types=[
                ExerciseTypeItem(type_id="ET001", name="跑步", tier="primary", rationale="改善注意力"),
                ExerciseTypeItem(type_id="ET002", name="游泳", tier="secondary"),
            ],
            child_age_group="6-8岁",
        )
        assert len(data.exercise_types) == 2
        assert data.child_age_group == "6-8岁"

    def test_empty_exercise_types_rejected(self):
        """min_length=1 确保至少有一个推荐"""
        from src.schemas.knowledge_qa import Section3StructuredData

        with pytest.raises(ValidationError):
            Section3StructuredData(exercise_types=[])

    def test_section3_response_structured_data_typed(self):
        from src.schemas.knowledge_qa import Section3Response, Section3StructuredData

        resp = Section3Response(
            content="## 运动推荐",
            structured_data=Section3StructuredData(
                exercise_types=[{"type_id": "ET001", "name": "跑步", "tier": "primary"}]
            ),
        )
        assert isinstance(resp.structured_data, Section3StructuredData)

    def test_section3_response_backward_compat_dict(self):
        from src.schemas.knowledge_qa import Section3Response, Section3StructuredData

        resp = Section3Response(
            content="## 运动推荐",
            structured_data={
                "exercise_types": [{"type_id": "ET001", "name": "跑步", "tier": "primary"}],
                "child_age_group": "6-8岁",
            },
        )
        assert isinstance(resp.structured_data, Section3StructuredData)


# ==================== P2-2: IntensityLevel 枚举 ====================


class TestIntensityLevel:
    """IntensityLevel 枚举 + 映射函数测试"""

    def test_enum_values(self):
        from src.schemas.knowledge_qa import IntensityLevel

        assert IntensityLevel.LOW.value == "low"
        assert IntensityLevel.MODERATE.value == "moderate"
        assert IntensityLevel.HIGH.value == "high"

    def test_map_exact_chinese(self):
        from src.schemas.knowledge_qa import map_intensity, IntensityLevel

        assert map_intensity("低强度") == IntensityLevel.LOW
        assert map_intensity("中低强度") == IntensityLevel.LOW_MODERATE
        assert map_intensity("中强度") == IntensityLevel.MODERATE
        assert map_intensity("中高强度") == IntensityLevel.MODERATE_HIGH
        assert map_intensity("高强度") == IntensityLevel.HIGH

    def test_map_with_parentheses(self):
        """带括号描述的强度值也能正确映射"""
        from src.schemas.knowledge_qa import map_intensity, IntensityLevel

        assert map_intensity("中强度（最大心率65%-75%）") == IntensityLevel.MODERATE
        assert map_intensity("高强度耐力") == IntensityLevel.HIGH

    def test_map_prefix_fallback(self):
        """前缀匹配兜底"""
        from src.schemas.knowledge_qa import map_intensity, IntensityLevel

        result = map_intensity("中-高强度")
        assert result in (IntensityLevel.MODERATE_HIGH, IntensityLevel.MODERATE)

    def test_map_empty_returns_none(self):
        from src.schemas.knowledge_qa import map_intensity

        assert map_intensity("") is None
        assert map_intensity(None) is None

    def test_map_unknown_returns_none(self):
        from src.schemas.knowledge_qa import map_intensity

        assert map_intensity("完全未知") is None


# ==================== P2-3: 运动名称模糊匹配统一 ====================


class TestFuzzyMatchExercise:
    """fuzzy_match_exercise 公共函数测试"""

    def test_exact_match(self):
        from src.core.knowledge_qa.nodes.base import fuzzy_match_exercise

        names = ["跑步", "游泳", "瑜伽"]
        assert fuzzy_match_exercise("跑步", names) == "跑步"

    def test_case_insensitive_exact(self):
        from src.core.knowledge_qa.nodes.base import fuzzy_match_exercise

        names = ["跑步", "游泳"]
        assert fuzzy_match_exercise("  跑步  ", names) == "跑步"

    def test_substring_match(self):
        """LLM 输出是清单名称的子串"""
        from src.core.knowledge_qa.nodes.base import fuzzy_match_exercise

        names = ["蹦床跳跃休息（课间/工作间切换）"]
        assert fuzzy_match_exercise("蹦床跳跃", names) == "蹦床跳跃休息（课间/工作间切换）"

    def test_substring_reverse_match(self):
        """清单名称是 LLM 输出的子串"""
        from src.core.knowledge_qa.nodes.base import fuzzy_match_exercise

        names = ["慢跑"]
        assert fuzzy_match_exercise("慢跑30分钟", names) == "慢跑"

    def test_difflib_fuzzy_match(self):
        """difflib 序列匹配兜底"""
        from src.core.knowledge_qa.nodes.base import fuzzy_match_exercise

        names = ["散步（轻松步行）"]
        result = fuzzy_match_exercise("散步", names, cutoff=0.3)
        assert result == "散步（轻松步行）"

    def test_no_match_returns_none(self):
        from src.core.knowledge_qa.nodes.base import fuzzy_match_exercise

        names = ["跑步", "游泳", "瑜伽"]
        assert fuzzy_match_exercise("量子力学", names) is None

    def test_empty_inputs(self):
        from src.core.knowledge_qa.nodes.base import fuzzy_match_exercise

        assert fuzzy_match_exercise("", ["跑步"]) is None
        assert fuzzy_match_exercise("跑步", []) is None
        assert fuzzy_match_exercise(None, ["跑步"]) is None
