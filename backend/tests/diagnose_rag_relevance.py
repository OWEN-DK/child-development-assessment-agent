"""
RAG 搜索相关度计算诊断测试

目的：暴露当前相关度计算逻辑的问题
- 测试 relevance_score 与 Cross-Encoder 分数的相关性
- 测试 age_fit_score 的细粒度分布
- 测试分数混合导致的语义不清问题
"""

import sys
import os

# 添加项目路径
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, backend_dir)
sys.path.insert(0, os.path.join(backend_dir, "src"))

from src.core.child_development_engine import child_development_engine


def test_age_fit_score_granularity():
    """测试年龄适配度分数的细粒度"""
    print("\n" + "=" * 80)
    print("测试 1: 年龄适配度分数细粒度")
    print("=" * 80)

    test_contents = [
        "适合 3 岁儿童的精细动作训练，使用串珠游戏",
        "适合 4 岁儿童的语言表达训练，讲故事活动",
        "适合 5 岁儿童的认知发展训练，简单的数学游戏",
        "适合 6 岁儿童的社交技能训练，角色扮演游戏",
        "适合 2 岁儿童的大动作训练，爬行和走路练习",
        # 不包含明确年龄的内容
        "儿童注意力训练方法，通过游戏提高专注力",
        "亲子阅读技巧，培养孩子的阅读兴趣",
        "儿童情绪管理，帮助孩子学会表达情感",
    ]

    test_ages = [2, 3, 4, 5, 6]

    scores = set()
    print(f"\n{'内容':<40} {'年龄':<6} {'适配度':<8}")
    print("-" * 60)

    for content in test_contents:
        for age in test_ages:
            score = child_development_engine.calculate_age_appropriateness(content, age)
            scores.add(score)
            print(f"{content[:38]:<40} {age:<6} {score:<8.2f}")

    print(f"\n结果：年龄适配度分数仅有 {len(scores)} 个不同值：{sorted(scores)}")
    print(f"期望：应该有 ≥10 个不同值（细粒度连续分布）")

    if len(scores) < 10:
        print("❌ 失败：年龄适配度分数过于粗糙，仅三档固定值")
    else:
        print("✅ 通过：年龄适配度分数有细粒度分布")

    return len(scores) >= 10


def test_score_mixing_problem():
    """测试分数混合导致的问题"""
    print("\n" + "=" * 80)
    print("测试 2: 分数混合导致的语义不清问题")
    print("=" * 80)

    # 模拟不同场景
    test_cases = [
        {
            "name": "高相关性 + 高年龄适配",
            "base_score": 0.9,
            "age_fit_score": 1.0,
            "age_weight": 0.3,
        },
        {
            "name": "高相关性 + 低年龄适配",
            "base_score": 0.9,
            "age_fit_score": 0.5,
            "age_weight": 0.3,
        },
        {
            "name": "低相关性 + 高年龄适配",
            "base_score": 0.3,
            "age_fit_score": 1.0,
            "age_weight": 0.3,
        },
        {
            "name": "低相关性 + 低年龄适配",
            "base_score": 0.3,
            "age_fit_score": 0.5,
            "age_weight": 0.3,
        },
    ]

    print(
        f"\n{'场景':<25} {'基础分':<8} {'年龄适配':<8} {'年龄权重':<8} {'最终分':<8} {'问题'}"
    )
    print("-" * 80)

    problems_found = []

    for case in test_cases:
        base = case["base_score"]
        age_fit = case["age_fit_score"]
        age_weight = case["age_weight"]
        final = base * (1 - age_weight) + age_fit * age_weight

        problem = ""
        if case["name"] == "高相关性 + 低年龄适配":
            if final > 0.7:
                problem = "⚠️  高相关内容被年龄适配度拉低分数"
                problems_found.append(problem)
        elif case["name"] == "低相关性 + 高年龄适配":
            if final > 0.6:
                problem = "⚠️  低相关内容被年龄适配度拉高分数"
                problems_found.append(problem)

        print(
            f"{case['name']:<25} {base:<8.2f} {age_fit:<8.2f} {age_weight:<8.2f} {final:<8.2f} {problem}"
        )

    if problems_found:
        print(f"\n❌ 失败：发现 {len(problems_found)} 个分数混合问题")
        for p in problems_found:
            print(f"   - {p}")
    else:
        print("\n✅ 通过：分数混合逻辑合理")

    return len(problems_found) == 0


def test_relevance_score_semantic_clarity():
    """测试 relevance_score 的语义清晰度"""
    print("\n" + "=" * 80)
    print("测试 3: relevance_score 语义清晰度")
    print("=" * 80)

    print("\n问题：当前 relevance_score 是什么含义？")
    print("  A. 内容与查询的相关性")
    print("  B. 内容对用户年龄的适配度")
    print("  C. A 和 B 的混合")
    print("\n当前实现：C（混合分数）")
    print("问题：")
    print("  1. 用户看到 0.75 分，无法知道是因为相关还是不相关")
    print("  2. 开发者无法调试：是检索问题还是年龄过滤问题？")
    print("  3. 优化方向错误：在优化一个本身就有问题的公式")

    print("\n❌ 失败：relevance_score 语义不清，混合了两个不同维度的概念")
    return False


def test_age_filter_effectiveness():
    """测试年龄过滤的有效性"""
    print("\n" + "=" * 80)
    print("测试 4: 年龄过滤有效性")
    print("=" * 80)

    test_contents = [
        ("适合 3 岁儿童的精细动作训练", 3, True),
        ("适合 6 岁儿童的数学游戏", 3, False),
        ("适合 2 岁儿童的爬行练习", 3, False),
        ("儿童注意力训练方法", 3, True),  # 无明确年龄，应该返回默认值
    ]

    print(f"\n{'内容':<30} {'用户年龄':<8} {'期望过滤':<8} {'实际过滤':<8} {'结果'}")
    print("-" * 70)

    correct = 0
    total = len(test_contents)

    for content, user_age, should_pass in test_contents:
        is_suitable, reason = child_development_engine.filter_unsuitable_content(
            content, user_age
        )
        actually_passes = is_suitable

        result = "✅" if actually_passes == should_pass else "❌"
        if actually_passes == should_pass:
            correct += 1

        print(
            f"{content[:28]:<30} {user_age:<8} {str(should_pass):<8} {str(actually_passes):<8} {result}"
        )

    accuracy = correct / total if total > 0 else 0
    print(f"\n准确率：{accuracy:.0%} ({correct}/{total})")
    print(f"期望：≥90%")

    if accuracy >= 0.9:
        print("✅ 通过：年龄过滤准确率达标")
    else:
        print("❌ 失败：年龄过滤准确率不足")

    return accuracy >= 0.9


def test_score_distribution():
    """测试最终分数分布"""
    print("\n" + "=" * 80)
    print("测试 5: 最终分数分布分析")
    print("=" * 80)

    # 模拟 100 个检索结果的分数分布
    import random

    random.seed(42)

    base_scores = [random.uniform(0.3, 0.95) for _ in range(100)]
    age_fit_scores = [random.choice([0.5, 0.8, 1.0]) for _ in range(100)]
    age_weight = 0.3

    final_scores = [
        base * (1 - age_weight) + age_fit * age_weight
        for base, age_fit in zip(base_scores, age_fit_scores)
    ]

    # 分析分布
    print(f"\n基础分数统计：")
    print(f"  最小值：{min(base_scores):.3f}")
    print(f"  最大值：{max(base_scores):.3f}")
    print(f"  平均值：{sum(base_scores) / len(base_scores):.3f}")

    print(f"\n年龄适配度分数分布：")
    for score in [0.5, 0.8, 1.0]:
        count = age_fit_scores.count(score)
        print(f"  {score:.1f}: {count} 个 ({count}%)")

    print(f"\n最终分数统计：")
    print(f"  最小值：{min(final_scores):.3f}")
    print(f"  最大值：{max(final_scores):.3f}")
    print(f"  平均值：{sum(final_scores) / len(final_scores):.3f}")

    # 检查分数分布是否被年龄适配度扭曲
    # 如果基础分高但年龄适配度低，最终分应该仍然较高
    distorted_count = 0
    for base, age_fit, final in zip(base_scores, age_fit_scores, final_scores):
        if base > 0.8 and age_fit == 0.5 and final < 0.7:
            distorted_count += 1

    print(f"\n分数扭曲情况：")
    print(f"  高相关 (base>0.8) + 低年龄适配 (0.5) → 最终分 <0.7: {distorted_count} 个")

    if distorted_count > 0:
        print(f"❌ 失败：{distorted_count} 个高相关内容被年龄适配度拉低分数")
    else:
        print("✅ 通过：分数分布合理")

    return distorted_count == 0


def main():
    """运行所有诊断测试"""
    print("=" * 80)
    print("RAG 搜索相关度计算诊断测试")
    print("=" * 80)

    results = []

    # 运行测试
    results.append(("年龄适配度细粒度", test_age_fit_score_granularity()))
    results.append(("分数混合问题", test_score_mixing_problem()))
    results.append(
        ("relevance_score 语义清晰度", test_relevance_score_semantic_clarity())
    )
    results.append(("年龄过滤有效性", test_age_filter_effectiveness()))
    results.append(("最终分数分布", test_score_distribution()))

    # 汇总结果
    print("\n" + "=" * 80)
    print("诊断结果汇总")
    print("=" * 80)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    print(f"\n{'测试项':<30} {'结果':<8}")
    print("-" * 40)
    for name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{name:<30} {status}")

    print(f"\n总计：{passed}/{total} 通过")

    if passed < total:
        print(f"\n🔴 发现 {total - passed} 个问题，需要优化")
        print("\n核心问题：")
        print("  1. 年龄适配度分数仅三档固定值 (1.0/0.8/0.5)，缺乏细粒度")
        print("  2. relevance_score 混合了相关性和年龄适配度，语义不清")
        print("  3. 高相关内容可能被低年龄适配度拉低分数")
        print("  4. 无法区分检索问题和年龄过滤问题")
    else:
        print("\n✅ 所有测试通过，相关度计算逻辑合理")


if __name__ == "__main__":
    main()
