"""年龄适配度细粒度计算器单元测试"""

import pytest
import time
from src.core.rag.age_fit_scorer import AgeFitScorer

# 测试数据：不同年龄和内容组合
TEST_CONTENTS = [
    "适合 2 岁儿童的大动作训练，包括爬行和走路练习",
    "适合 3 岁儿童的精细动作训练，如穿珠子和画画",
    "适合 4 岁儿童的语言表达训练，通过故事讲述提高词汇量",
    "适合 5 岁儿童的认知发展训练，包括简单的逻辑推理游戏",
    "适合 6 岁儿童的社交技能训练，学习分享和合作",
    "儿童注意力训练方法，适合学龄前儿童",
    "亲子阅读技巧，培养早期语言发展",
    "儿童情绪管理，帮助幼儿学会表达情感",
    "适合 3-4 岁儿童的平衡训练，通过游戏提高协调能力",
    "适合 5-6 岁儿童的逻辑思维训练，包括分类和排序活动",
    "婴儿感官刺激，适合 0-1 岁宝宝的触觉和听觉发展",
    "学龄儿童学习方法指导，提高自主学习能力",
]


@pytest.fixture(autouse=True)
def clear_cache():
    """每个测试前清理缓存"""
    AgeFitScorer.calculate.cache_clear()
    yield
    AgeFitScorer.calculate.cache_clear()


def test_age_fit_score_granularity():
    """验证 age_fit_score 输出 ≥10 个不同值（细粒度连续分布）"""
    scores = set()

    # 使用 10 个不同年龄和内容组合
    test_cases = [
        (2, TEST_CONTENTS[0]),  # 2 岁 + 大动作
        (3, TEST_CONTENTS[1]),  # 3 岁 + 精细动作
        (4, TEST_CONTENTS[2]),  # 4 岁 + 语言
        (5, TEST_CONTENTS[3]),  # 5 岁 + 认知
        (6, TEST_CONTENTS[4]),  # 6 岁 + 社交
        (3, TEST_CONTENTS[5]),  # 3 岁 + 注意力
        (4, TEST_CONTENTS[6]),  # 4 岁 + 亲子阅读
        (5, TEST_CONTENTS[7]),  # 5 岁 + 情绪管理
        (3, TEST_CONTENTS[8]),  # 3 岁 + 平衡训练
        (6, TEST_CONTENTS[9]),  # 6 岁 + 逻辑思维
    ]

    for age, content in test_cases:
        score = AgeFitScorer.calculate(
            content=content,
            user_age=age,
            target_age_min=age - 1,
            target_age_max=age + 1,
        )
        scores.add(round(score, 3))  # 保留 3 位小数去重

    assert len(scores) >= 10, f"仅输出 {len(scores)} 个不同值，目标 ≥10"


@pytest.mark.parametrize(
    "age,content,target_min,target_max",
    [
        (0, TEST_CONTENTS[10], 0, 2),  # 0 岁边界
        (3, TEST_CONTENTS[1], 3, 4),  # 正常场景
        (6, TEST_CONTENTS[4], 5, 7),  # 6 岁边界
        (10, TEST_CONTENTS[11], 8, 12),  # 10 岁
        (18, TEST_CONTENTS[11], 15, 18),  # 18 岁边界
        (3, TEST_CONTENTS[0], 5, 6),  # 年龄不匹配
    ],
)
def test_age_fit_score_range(age, content, target_min, target_max):
    """验证 age_fit_score 输出在 [0, 1] 范围内"""
    score = AgeFitScorer.calculate(
        content=content,
        user_age=age,
        target_age_min=target_min,
        target_age_max=target_max,
    )
    assert 0.0 <= score <= 1.0, f"分数 {score} 超出 [0, 1] 范围"


def test_perfect_match_score():
    """验证用户年龄在目标范围内时，分数 >0.5"""
    test_cases = [
        (3, TEST_CONTENTS[1], 3, 4),  # 3 岁在 [3,4] 内
        (4, TEST_CONTENTS[2], 3, 5),  # 4 岁在 [3,5] 内
        (5, TEST_CONTENTS[3], 4, 6),  # 5 岁在 [4,6] 内
        (6, TEST_CONTENTS[4], 5, 7),  # 6 岁在 [5,7] 内
    ]

    for age, content, target_min, target_max in test_cases:
        score = AgeFitScorer.calculate(
            content=content,
            user_age=age,
            target_age_min=target_min,
            target_age_max=target_max,
        )
        assert score > 0.5, (
            f"年龄 {age} 在 [{target_min},{target_max}] 内，分数 {score} 应 >0.5"
        )


def test_complete_mismatch_score():
    """验证年龄差 ≥5 岁时，分数 <0.3"""
    test_cases = [
        (0, TEST_CONTENTS[4], 5, 7),  # 0 岁 vs [5,7]
        (2, TEST_CONTENTS[9], 8, 10),  # 2 岁 vs [8,10]
        (8, TEST_CONTENTS[0], 0, 2),  # 8 岁 vs [0,2]
        (12, TEST_CONTENTS[1], 2, 4),  # 12 岁 vs [2,4]
    ]

    for age, content, target_min, target_max in test_cases:
        score = AgeFitScorer.calculate(
            content=content,
            user_age=age,
            target_age_min=target_min,
            target_age_max=target_max,
        )
        assert score < 0.3, f"年龄差 ≥5 岁，分数 {score} 应 <0.3"


def test_calculation_performance():
    """验证单次计算耗时 ≤5ms"""
    content = TEST_CONTENTS[1]
    iterations = 100

    start_time = time.perf_counter()
    for _ in range(iterations):
        AgeFitScorer.calculate(
            content=content, user_age=3, target_age_min=2, target_age_max=4
        )
    elapsed_ms = (time.perf_counter() - start_time) * 1000 / iterations

    assert elapsed_ms <= 5.0, f"单次计算耗时 {elapsed_ms:.2f}ms，目标 ≤5ms"


def test_boundary_cases():
    """验证边界场景处理正确"""
    # 0 岁婴儿
    score_0 = AgeFitScorer.calculate(
        content=TEST_CONTENTS[10], user_age=0, target_age_min=0, target_age_max=2
    )
    assert score_0 > 0.5, "0 岁婴儿内容对 0 岁用户应高分"

    # 18 岁边界
    score_18 = AgeFitScorer.calculate(
        content=TEST_CONTENTS[11], user_age=18, target_age_min=15, target_age_max=18
    )
    assert score_18 > 0.5, "18 岁内容对 18 岁用户应高分"

    # 无明确年龄内容（target_min=0, target_max=18）
    score_general = AgeFitScorer.calculate(
        content=TEST_CONTENTS[5], user_age=3, target_age_min=0, target_age_max=18
    )
    assert 0.3 <= score_general <= 0.9, "通用内容应给中等偏上分数"

    # 单年龄内容（target_min == target_max）
    score_single = AgeFitScorer.calculate(
        content=TEST_CONTENTS[0], user_age=2, target_age_min=2, target_age_max=2
    )
    assert score_single > 0.5, "单年龄内容对匹配年龄用户应高分"


def test_three_dimensions_independence():
    """验证三个维度独立计算，互不影响"""
    # 测试维度 1（年龄范围匹配）
    dim1 = AgeFitScorer._calculate_age_range_match(
        user_age=3, target_min=3, target_max=4
    )
    assert 0.35 <= dim1 <= 0.4, f"维度 1 分数 {dim1} 不在 [0.35, 0.4] 范围内"

    # 测试维度 2（内容特征适配）
    dim2 = AgeFitScorer._calculate_content_feature_fit(
        content=TEST_CONTENTS[1], user_age=3
    )
    assert 0.0 <= dim2 <= 0.3, f"维度 2 分数 {dim2} 不在 [0, 0.3] 范围内"

    # 测试维度 3（领域匹配）
    dim3 = AgeFitScorer._calculate_domain_match(
        content=TEST_CONTENTS[1], user_age=3, metadata={"topics": ["精细动作"]}
    )
    assert 0.0 <= dim3 <= 0.3, f"维度 3 分数 {dim3} 不在 [0, 0.3] 范围内"

    # 验证总分 = 维度 1 + 维度 2 + 维度 3
    total = AgeFitScorer.calculate(
        content=TEST_CONTENTS[1],
        user_age=3,
        target_age_min=3,
        target_age_max=4,
        metadata_str='{"topics": ["精细动作"]}',
    )
    assert abs(total - (dim1 + dim2 + dim3)) < 0.001, "总分应等于三维度之和"


def test_cache_hit_performance():
    """验证缓存命中后的计算性能"""
    # 首次计算（缓存未命中）
    content = "适合 3 岁儿童的精细动作训练，如穿珠子和画画"
    start = time.perf_counter()
    AgeFitScorer.calculate(
        content=content, user_age=3, target_age_min=2, target_age_max=4
    )
    first_call_ms = (time.perf_counter() - start) * 1000

    # 第二次计算（缓存命中）
    start = time.perf_counter()
    AgeFitScorer.calculate(
        content=content, user_age=3, target_age_min=2, target_age_max=4
    )
    cache_hit_ms = (time.perf_counter() - start) * 1000

    # 缓存命中应显著快于首次计算
    assert cache_hit_ms < 0.1, f"缓存命中耗时 {cache_hit_ms:.3f}ms，目标 <0.1ms"


def test_cache_clear():
    """验证缓存清理功能"""
    # 填充缓存
    for age in range(10):
        AgeFitScorer.calculate(
            content=f"测试内容{age}",
            user_age=age,
            target_age_min=age,
            target_age_max=age + 1,
        )

    # 清理缓存
    AgeFitScorer.calculate.cache_clear()

    # 验证缓存已清空（通过 info 方法）
    cache_info = AgeFitScorer.calculate.cache_info()
    assert cache_info.currsize == 0, "缓存应已清空"
