"""
年龄过滤器单元测试
"""

import pytest
from src.core.age_filter import AgeFilter, AgeFilterMode


# 需求文档测试 11 的 7 条数据
# 严格模式期望基于计划验证表（100% 准确率）
# 宽松模式期望基于实际逻辑（tolerance=2 for range, 1 for single age）
TEST_CASES = [
    # (user_age, target_min, target_max, strict_expected, loose_expected, description)
    (3, 3, 4, False, False, "适合 3 岁儿童的精细动作训练"),
    (3, 6, 6, True, True, "适合 6 岁儿童的数学游戏"),
    (3, 2, 2, True, False, "适合 2 岁儿童的爬行练习"),
    (3, 0, 18, False, False, "儿童注意力训练方法（无明确年龄）"),
    (3, 4, 5, True, False, "适合 4-5 岁儿童的语言训练"),  # loose: 3 ∈ [2,7] → 通过
    (3, 3, 4, False, False, "适合 3-4 岁儿童的平衡训练"),
    (3, 0, 2, True, False, "适合 0-2 岁婴儿的感官刺激"),  # loose: 3 ∈ [-2,4] → 通过
]


@pytest.mark.parametrize(
    "user_age,target_min,target_max,strict_expected,loose_expected,description",
    TEST_CASES,
)
def test_age_filter_standard_cases(
    user_age, target_min, target_max, strict_expected, loose_expected, description
):
    """验证 7 个标准测试用例的过滤行为"""
    # 严格模式
    strict_result = AgeFilter.should_filter(
        target_min, target_max, user_age, AgeFilterMode.STRICT
    )
    assert strict_result == strict_expected, (
        f"用例 '{description}' 严格模式失败：期望 {'过滤' if strict_expected else '通过'}，"
        f"实际 {'过滤' if strict_result else '通过'}"
    )

    # 宽松模式
    loose_result = AgeFilter.should_filter(
        target_min, target_max, user_age, AgeFilterMode.LOOSE
    )
    assert loose_result == loose_expected, (
        f"用例 '{description}' 宽松模式失败：期望 {'过滤' if loose_expected else '通过'}，"
        f"实际 {'过滤' if loose_result else '通过'}"
    )


def test_strict_mode_accuracy():
    """验证严格模式准确率 ≥90%"""
    passed = 0
    total = len(TEST_CASES)

    for user_age, target_min, target_max, strict_expected, _, _ in TEST_CASES:
        result = AgeFilter.should_filter(
            target_min, target_max, user_age, AgeFilterMode.STRICT
        )
        if result == strict_expected:
            passed += 1

    accuracy = passed / total
    assert accuracy >= 0.9, f"严格模式准确率 {accuracy:.0%} ({passed}/{total}) < 90%"


def test_boundary_cases():
    """验证边界场景处理正确"""
    # 0 岁用户
    assert (
        AgeFilter.should_filter(0, 2, 0, AgeFilterMode.STRICT) == False
    )  # 通过：0 ∈ [0, 2]
    assert (
        AgeFilter.should_filter(3, 5, 0, AgeFilterMode.STRICT) == True
    )  # 过滤：0 ∉ [3, 5]

    # 18 岁用户
    assert (
        AgeFilter.should_filter(15, 18, 18, AgeFilterMode.STRICT) == False
    )  # 通过：18 ∈ [15, 18]
    assert (
        AgeFilter.should_filter(0, 5, 18, AgeFilterMode.STRICT) == True
    )  # 过滤：18 ∉ [0, 5]

    # 无明确年龄内容
    assert AgeFilter.should_filter(0, 18, 5, AgeFilterMode.STRICT) == False  # 通过
    assert AgeFilter.should_filter(0, 18, 10, AgeFilterMode.STRICT) == False  # 通过

    # 单年龄内容
    assert (
        AgeFilter.should_filter(3, 3, 3, AgeFilterMode.STRICT) == False
    )  # 通过：3 ∈ [3, 3]
    assert (
        AgeFilter.should_filter(3, 3, 4, AgeFilterMode.STRICT) == True
    )  # 过滤：4 ∉ [3, 3]
    assert (
        AgeFilter.should_filter(3, 3, 4, AgeFilterMode.LOOSE) == False
    )  # 通过：4 ∈ [2, 4]


def test_mode_switching():
    """验证严格/宽松模式切换行为正确"""
    # 严格模式：user_age=2, target=[2,3] → 2 ∈ [2, 3] → 通过
    assert AgeFilter.should_filter(2, 3, 2, AgeFilterMode.STRICT) == False  # 通过
    assert AgeFilter.should_filter(2, 3, 2, AgeFilterMode.LOOSE) == False  # 通过

    # 严格模式：user_age=0, target=[2,3] → 0 ∉ [2, 3] → 过滤
    assert AgeFilter.should_filter(2, 3, 0, AgeFilterMode.STRICT) == True  # 过滤
    # 宽松模式：user_age=0, target=[2,3] → 0 ∈ [0, 5] → 通过
    assert AgeFilter.should_filter(2, 3, 0, AgeFilterMode.LOOSE) == False  # 通过


def test_invalid_user_age():
    """验证无效用户年龄处理"""
    # 负数年龄应该被过滤
    assert AgeFilter.should_filter(3, 4, -1, AgeFilterMode.STRICT) == True
    assert AgeFilter.should_filter(3, 4, -5, AgeFilterMode.LOOSE) == True


def test_unspecified_age_content():
    """验证无明确年龄内容处理"""
    # 默认范围 [0, 18] 的内容应该始终通过
    for age in [0, 3, 6, 12, 18]:
        assert AgeFilter.should_filter(0, 18, age, AgeFilterMode.STRICT) == False
        assert AgeFilter.should_filter(0, 18, age, AgeFilterMode.LOOSE) == False


def test_single_age_content():
    """验证单年龄内容处理"""
    # 单年龄内容 [3, 3]
    assert AgeFilter.should_filter(3, 3, 3, AgeFilterMode.STRICT) == False  # 正好匹配
    assert (
        AgeFilter.should_filter(3, 3, 2, AgeFilterMode.STRICT) == True
    )  # 严格模式 tolerance=0
    assert (
        AgeFilter.should_filter(3, 3, 2, AgeFilterMode.LOOSE) == False
    )  # 宽松模式 tolerance=1
    assert (
        AgeFilter.should_filter(3, 3, 4, AgeFilterMode.STRICT) == True
    )  # 严格模式 tolerance=0
    assert (
        AgeFilter.should_filter(3, 3, 4, AgeFilterMode.LOOSE) == False
    )  # 宽松模式 tolerance=1


def test_range_age_content():
    """验证范围年龄内容处理"""
    # 范围内容 [3, 5]
    assert AgeFilter.should_filter(3, 5, 3, AgeFilterMode.STRICT) == False  # 在范围内
    assert AgeFilter.should_filter(3, 5, 4, AgeFilterMode.STRICT) == False  # 在范围内
    assert AgeFilter.should_filter(3, 5, 5, AgeFilterMode.STRICT) == False  # 在范围内
    assert (
        AgeFilter.should_filter(3, 5, 6, AgeFilterMode.STRICT) == True
    )  # 6 ∉ [3, 5]，超过最大年龄
    assert (
        AgeFilter.should_filter(3, 5, 7, AgeFilterMode.STRICT) == True
    )  # 7 ∉ [3, 5]，超过最大年龄
    assert (
        AgeFilter.should_filter(3, 5, 2, AgeFilterMode.STRICT) == True
    )  # 2 ∉ [3, 5]，低于最小年龄
    assert (
        AgeFilter.should_filter(3, 5, 1, AgeFilterMode.STRICT) == True
    )  # 1 ∉ [3, 5]，低于最小年龄
