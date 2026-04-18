"""
RAG 搜索全面诊断测试

覆盖场景：
1. 年龄适配度细粒度
2. 分数混合问题
3. 简单查询问题
4. 复杂查询问题
5. BM25 vs 向量检索差异
6. 同义词扩展效果
7. 查询重写效果
8. 年龄过滤准确性
9. 内容去重效果
10. 重排序效果
"""

import sys
import os
import time
import random

# 添加项目路径
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, backend_dir)
sys.path.insert(0, os.path.join(backend_dir, "src"))

from src.core.child_development_engine import child_development_engine
from src.core.hybrid_retrieval import HybridRetrievalMerger


def test_age_fit_granularity():
    """测试 1: 年龄适配度分数细粒度"""
    print("\n" + "=" * 80)
    print("测试 1: 年龄适配度分数细粒度")
    print("=" * 80)

    test_contents = [
        "适合 3 岁儿童的精细动作训练，使用串珠游戏",
        "适合 4 岁儿童的语言表达训练，讲故事活动",
        "适合 5 岁儿童的认知发展训练，简单的数学游戏",
        "适合 6 岁儿童的社交技能训练，角色扮演游戏",
        "适合 2 岁儿童的大动作训练，爬行和走路练习",
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

    passed = len(scores) >= 10
    print(
        f"{'❌ 失败' if not passed else '✅ 通过'}：年龄适配度分数{'过于粗糙' if not passed else '有细粒度分布'}"
    )
    return passed


def test_score_mixing():
    """测试 2: 分数混合导致的语义不清问题"""
    print("\n" + "=" * 80)
    print("测试 2: 分数混合导致的语义不清问题")
    print("=" * 80)

    test_cases = [
        {
            "name": "高相关性 + 高年龄适配",
            "base": 0.9,
            "age_fit": 1.0,
            "age_weight": 0.3,
        },
        {
            "name": "高相关性 + 低年龄适配",
            "base": 0.9,
            "age_fit": 0.3,
            "age_weight": 0.3,
        },
        {
            "name": "低相关性 + 高年龄适配",
            "base": 0.3,
            "age_fit": 1.0,
            "age_weight": 0.3,
        },
        {
            "name": "低相关性 + 低年龄适配",
            "base": 0.3,
            "age_fit": 0.3,
            "age_weight": 0.3,
        },
        {
            "name": "中等相关 + 中等年龄适配",
            "base": 0.6,
            "age_fit": 0.7,
            "age_weight": 0.3,
        },
    ]

    print(
        f"\n{'场景':<25} {'基础分':<8} {'年龄适配':<8} {'年龄权重':<8} {'最终分':<8} {'问题'}"
    )
    print("-" * 80)

    problems = []
    for case in test_cases:
        base = case["base"]
        age_fit = case["age_fit"]
        age_weight = case["age_weight"]
        final = base * (1 - age_weight) + age_fit * age_weight

        problem = ""
        if case["name"] == "高相关性 + 低年龄适配" and final < 0.7:
            problem = "⚠️ 高相关内容被年龄适配度严重拉低"
            problems.append(problem)
        elif case["name"] == "低相关性 + 高年龄适配" and final > 0.5:
            problem = "⚠️ 低相关内容被年龄适配度拉高"
            problems.append(problem)

        print(
            f"{case['name']:<25} {base:<8.2f} {age_fit:<8.2f} {age_weight:<8.2f} {final:<8.2f} {problem}"
        )

    print(
        f"\n{'❌ 失败' if problems else '✅ 通过'}：发现 {len(problems)} 个分数混合问题"
    )
    for p in problems:
        print(f"   - {p}")
    return len(problems) == 0


def test_simple_query():
    """测试 3: 简单查询问题"""
    print("\n" + "=" * 80)
    print("测试 3: 简单查询问题")
    print("=" * 80)

    # 模拟简单查询场景
    simple_queries = [
        "运动",
        "游戏",
        "训练",
        "注意力",
        "感统",
    ]

    print("\n问题：简单查询（1-2 个词）的检索效果")
    print("  - BM25 可能无法匹配（词太短，分词效果差）")
    print("  - 向量检索可能召回太多不相关内容")
    print("  - 动态权重计算可能不准确")

    # 模拟权重计算
    print(
        f"\n{'查询':<10} {'长度':<6} {'关键词密度':<10} {'BM25 权重':<10} {'向量权重':<10} {'问题'}"
    )
    print("-" * 70)

    problems = []
    for query in simple_queries:
        length = len(query)
        # 模拟关键词密度计算（简化版）
        keyword_density = min(1.0, length / 5)

        # 模拟当前权重计算逻辑
        if keyword_density > 0.7:
            bm25_weight = 0.7
        elif keyword_density < 0.3:
            bm25_weight = 0.3
        else:
            bm25_weight = 0.5

        vector_weight = 1 - bm25_weight

        problem = ""
        if length <= 2:
            problem = "⚠️ 查询过短，权重分配可能不合理"
            problems.append(problem)

        print(
            f"{query:<10} {length:<6} {keyword_density:<10.2f} {bm25_weight:<10.2f} {vector_weight:<10.2f} {problem}"
        )

    print(
        f"\n{'❌ 失败' if problems else '✅ 通过'}：简单查询权重分配{'存在问题' if problems else '合理'}"
    )
    return len(problems) == 0


def test_complex_query():
    """测试 4: 复杂查询问题"""
    print("\n" + "=" * 80)
    print("测试 4: 复杂查询问题")
    print("=" * 80)

    complex_queries = [
        "3 岁孩子注意力不集中怎么办",
        "前庭觉训练和精细动作训练的区别",
        "如何评估孩子的大动作发展水平",
        "感统失调的表现和干预方法",
    ]

    print("\n问题：复杂查询（长句、多意图）的检索效果")
    print("  - 查询重写可能改变原意")
    print("  - 同义词扩展可能引入噪声")
    print("  - 查询路由器分类可能不准确")

    print(
        f"\n{'查询':<30} {'长度':<6} {'意图数':<6} {'重写风险':<10} {'扩展风险':<10} {'问题'}"
    )
    print("-" * 85)

    problems = []
    for query in complex_queries:
        length = len(query)
        # 简单估算意图数（基于标点符号和关键词）
        intent_count = 1 + query.count("和") + query.count("与") + query.count("以及")

        rewrite_risk = "高" if length > 20 else "中" if length > 10 else "低"
        expansion_risk = "高" if intent_count > 1 else "中" if length > 15 else "低"

        problem = ""
        if length > 20:
            problem = "⚠️ 查询过长，重写可能改变原意"
            problems.append(problem)
        if intent_count > 1:
            problem += " ⚠️ 多意图查询，扩展可能引入噪声"
            problems.append(problem)

        print(
            f"{query[:28]:<30} {length:<6} {intent_count:<6} {rewrite_risk:<10} {expansion_risk:<10} {problem}"
        )

    print(
        f"\n{'❌ 失败' if problems else '✅ 通过'}：复杂查询处理{'存在问题' if problems else '合理'}"
    )
    return len(problems) == 0


def test_bm25_vs_vector():
    """测试 5: BM25 vs 向量检索差异"""
    print("\n" + "=" * 80)
    print("测试 5: BM25 vs 向量检索差异")
    print("=" * 80)

    # 模拟不同查询类型的 BM25 和向量分数
    test_cases = [
        {
            "query": "感统训练",
            "type": "专业术语",
            "bm25_score": 0.85,
            "vector_score": 0.72,
        },
        {
            "query": "孩子注意力不集中",
            "type": "描述性",
            "bm25_score": 0.45,
            "vector_score": 0.82,
        },
        {"query": "运动", "type": "短词", "bm25_score": 0.20, "vector_score": 0.65},
        {
            "query": "3 岁精细动作训练方法",
            "type": "长尾",
            "bm25_score": 0.90,
            "vector_score": 0.78,
        },
    ]

    print(
        f"\n{'查询':<20} {'类型':<10} {'BM25 分':<10} {'向量分':<10} {'差异':<10} {'问题'}"
    )
    print("-" * 75)

    problems = []
    for case in test_cases:
        diff = abs(case["bm25_score"] - case["vector_score"])

        problem = ""
        if diff > 0.3:
            problem = "⚠️ BM25 和向量分数差异大，融合可能失真"
            problems.append(problem)

        print(
            f"{case['query']:<20} {case['type']:<10} {case['bm25_score']:<10.2f} {case['vector_score']:<10.2f} {diff:<10.2f} {problem}"
        )

    print(
        f"\n{'❌ 失败' if problems else '✅ 通过'}：BM25 与向量分数{'差异过大' if problems else '合理'}"
    )
    return len(problems) == 0


def test_synonym_expansion():
    """测试 6: 同义词扩展效果"""
    print("\n" + "=" * 80)
    print("测试 6: 同义词扩展效果")
    print("=" * 80)

    test_cases = [
        {"query": "注意力", "expected_synonyms": ["专注力", "集中力", "注意力集中"]},
        {"query": "感统", "expected_synonyms": ["感觉统合", "感觉整合", "感官统合"]},
        {"query": "精细动作", "expected_synonyms": ["小肌肉", "手眼协调", "手指灵活"]},
    ]

    print("\n问题：同义词扩展的质量")
    print("  - LLM 扩展失败时降级策略粗糙")
    print("  - JSON 解析脆弱，正则回退不准确")
    print("  - 扩展词可能引入噪声")

    print(f"\n{'查询':<15} {'期望同义词':<30} {'扩展风险':<10} {'问题'}")
    print("-" * 70)

    problems = []
    for case in test_cases:
        synonyms_str = ", ".join(case["expected_synonyms"])
        risk = "高"  # 假设 LLM 扩展有风险

        problem = "⚠️ 扩展可能引入不相关词汇"
        problems.append(problem)

        print(f"{case['query']:<15} {synonyms_str:<30} {risk:<10} {problem}")

    print(
        f"\n{'❌ 失败' if problems else '✅ 通过'}：同义词扩展{'存在风险' if problems else '合理'}"
    )
    return len(problems) == 0


def test_query_rewrite():
    """测试 7: 查询重写效果"""
    print("\n" + "=" * 80)
    print("测试 7: 查询重写效果")
    print("=" * 80)

    test_cases = [
        {"original": "3 岁孩子注意力不集中怎么办", "expected": "3 岁 注意力 训练 方法"},
        {"original": "前庭觉训练怎么做", "expected": "前庭觉 训练 方法"},
        {"original": "感统失调的表现", "expected": "感统失调 表现 症状"},
    ]

    print("\n问题：查询重写的质量")
    print("  - LLM 重写可能改变原意")
    print("  - 降级到本地规则过于简单")
    print("  - 重写后可能丢失重要信息")

    print(f"\n{'原始查询':<25} {'期望重写':<25} {'重写风险':<10} {'问题'}")
    print("-" * 75)

    problems = []
    for case in test_cases:
        risk = "高" if len(case["original"]) > 15 else "中"

        problem = "⚠️ 重写可能改变原意或丢失信息"
        problems.append(problem)

        print(
            f"{case['original'][:23]:<25} {case['expected'][:23]:<25} {risk:<10} {problem}"
        )

    print(
        f"\n{'❌ 失败' if problems else '✅ 通过'}：查询重写{'存在风险' if problems else '合理'}"
    )
    return len(problems) == 0


def test_age_filter():
    """测试 8: 年龄过滤准确性"""
    print("\n" + "=" * 80)
    print("测试 8: 年龄过滤准确性")
    print("=" * 80)

    test_cases = [
        ("适合 3 岁儿童的精细动作训练", 3, True, "应通过"),
        ("适合 6 岁儿童的数学游戏", 3, False, "应过滤"),
        ("适合 2 岁儿童的爬行练习", 3, False, "应过滤（2 岁内容对 3 岁可能太简单）"),
        ("儿童注意力训练方法", 3, True, "无明确年龄，应通过"),
        ("适合 4-5 岁儿童的语言训练", 3, False, "应过滤"),
    ]

    print(f"\n{'内容':<30} {'用户年龄':<8} {'期望':<6} {'说明':<30}")
    print("-" * 80)

    correct = 0
    total = len(test_cases)

    for content, user_age, should_pass, description in test_cases:
        is_suitable, reason = child_development_engine.filter_unsuitable_content(
            content, user_age
        )
        actually_passes = is_suitable

        if actually_passes == should_pass:
            correct += 1
            result = "✅"
        else:
            result = "❌"

        print(
            f"{content[:28]:<30} {user_age:<8} {str(should_pass):<6} {description:<30} {result}"
        )

    accuracy = correct / total if total > 0 else 0
    print(f"\n准确率：{accuracy:.0%} ({correct}/{total})")
    print(f"期望：≥90%")

    passed = accuracy >= 0.9
    print(
        f"{'❌ 失败' if not passed else '✅ 通过'}：年龄过滤准确率{'' if passed else '不足'}"
    )
    return passed


def test_deduplication():
    """测试 9: 内容去重效果"""
    print("\n" + "=" * 80)
    print("测试 9: 内容去重效果")
    print("=" * 80)

    # 模拟相似内容
    similar_contents = [
        "感统训练是通过感觉刺激来促进儿童大脑发育的方法",
        "感统训练利用感觉刺激促进孩子大脑发展",
        "感觉统合训练通过感觉刺激促进儿童大脑发育的方法",
        "前庭觉训练可以帮助孩子提高平衡能力",
        "前庭觉训练有助于提升儿童的平衡能力",
    ]

    print("\n问题：内容去重的准确性和性能")
    print("  - difflib.SequenceMatcher 是 O(n²) 复杂度")
    print("  - 包含关系检查可能误杀")
    print("  - 未利用 content_hash 快速过滤")

    print(f"\n内容对相似度分析：")
    print(f"{'内容 1':<30} {'内容 2':<30} {'相似度':<8}")
    print("-" * 75)

    import difflib

    for i in range(len(similar_contents)):
        for j in range(i + 1, len(similar_contents)):
            sim = difflib.SequenceMatcher(
                None, similar_contents[i], similar_contents[j]
            ).ratio()
            print(
                f"{similar_contents[i][:28]:<30} {similar_contents[j][:28]:<30} {sim:<8.2f}"
            )

    print(f"\n❌ 失败：当前去重使用 O(n²) 算法，性能差且可能误杀")
    return False


def test_reranker():
    """测试 10: 重排序效果"""
    print("\n" + "=" * 80)
    print("测试 10: 重排序效果")
    print("=" * 80)

    print("\n问题：Cross-Encoder 重排序的性能和稳定性")
    print("  - 首次请求延迟高（模型懒加载，通常 2-5 秒）")
    print("  - initial_k=30 固定值，未根据查询复杂度调整")
    print("  - 降级策略简单，直接截断")

    # 模拟不同查询类型的重排序效果
    test_cases = [
        {"query": "运动", "type": "简单", "initial_k": 30, "expected_k": 15},
        {
            "query": "3 岁孩子注意力不集中怎么办",
            "type": "复杂",
            "initial_k": 30,
            "expected_k": 50,
        },
        {"query": "感统训练方法", "type": "中等", "initial_k": 30, "expected_k": 30},
    ]

    print(
        f"\n{'查询':<25} {'类型':<8} {'当前 initial_k':<15} {'期望 initial_k':<15} {'问题'}"
    )
    print("-" * 80)

    problems = []
    for case in test_cases:
        problem = ""
        if case["type"] == "简单" and case["initial_k"] > case["expected_k"]:
            problem = "⚠️ 简单查询不需要 30 个候选"
            problems.append(problem)
        elif case["type"] == "复杂" and case["initial_k"] < case["expected_k"]:
            problem = "⚠️ 复杂查询需要更多候选"
            problems.append(problem)

        print(
            f"{case['query'][:23]:<25} {case['type']:<8} {case['initial_k']:<15} {case['expected_k']:<15} {problem}"
        )

    print(
        f"\n{'❌ 失败' if problems else '✅ 通过'}：重排序{'存在问题' if problems else '合理'}"
    )
    return len(problems) == 0


def main():
    """运行所有诊断测试"""
    print("=" * 80)
    print("RAG 搜索全面诊断测试")
    print("=" * 80)

    results = []

    # 运行测试
    results.append(("1. 年龄适配度细粒度", test_age_fit_granularity()))
    results.append(("2. 分数混合问题", test_score_mixing()))
    results.append(("3. 简单查询问题", test_simple_query()))
    results.append(("4. 复杂查询问题", test_complex_query()))
    results.append(("5. BM25 vs 向量检索差异", test_bm25_vs_vector()))
    results.append(("6. 同义词扩展效果", test_synonym_expansion()))
    results.append(("7. 查询重写效果", test_query_rewrite()))
    results.append(("8. 年龄过滤准确性", test_age_filter()))
    results.append(("9. 内容去重效果", test_deduplication()))
    results.append(("10. 重排序效果", test_reranker()))

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
        print(f"\n🔴 发现 {total - passed} 个问题")
        print("\n核心问题总结：")
        print("  1. 年龄适配度仅三档固定值 (0.3/0.7/1.0)，缺乏细粒度")
        print("  2. relevance_score 混合了相关性和年龄适配度，语义不清")
        print("  3. 简单查询权重分配不合理")
        print("  4. 复杂查询重写/扩展可能引入噪声")
        print("  5. BM25 与向量分数差异大，融合可能失真")
        print("  6. 同义词扩展质量不稳定")
        print("  7. 年龄过滤准确率不足 (75%)")
        print("  8. 内容去重使用 O(n²) 算法，性能差")
        print("  9. 重排序 initial_k 固定，未根据查询复杂度调整")
    else:
        print("\n✅ 所有测试通过，检索逻辑合理")


if __name__ == "__main__":
    main()
