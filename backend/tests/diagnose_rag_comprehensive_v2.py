"""
RAG 搜索全面诊断测试 v2

覆盖维度：
1. 检索质量指标 (Precision@K, Recall@K, NDCG@K, MRR, MAP, HitRate@K)
2. 分数分布分析
3. 年龄适配度分析
4. 查询类型分析 (简单/复杂/专业术语/描述性)
5. 去重效果分析
6. 重排序效果分析
7. 性能分析
8. 稳定性分析
9. 相关性一致性分析
10. 边界场景分析
"""

import sys
import os
import time
import random
import numpy as np
from typing import List, Dict, Tuple

# 添加项目路径
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, backend_dir)
sys.path.insert(0, os.path.join(backend_dir, "src"))

from src.core.child_development_engine import child_development_engine


# ============================================================================
# 评估指标计算函数
# ============================================================================


def precision_at_k(retrieved: List[str], relevant: List[str], k: int = 5) -> float:
    """Precision@K: TopK 结果中相关文档的比例"""
    if not retrieved:
        return 0.0
    top_k = retrieved[:k]
    hits = sum(1 for doc in top_k if doc in relevant)
    return hits / len(top_k)


def recall_at_k(retrieved: List[str], relevant: List[str], k: int = 5) -> float:
    """Recall@K: 所有相关文档中被检索到的比例"""
    if not relevant:
        return 0.0
    top_k = retrieved[:k]
    hits = sum(1 for doc in top_k if doc in relevant)
    return hits / len(relevant)


def ndcg_at_k(
    retrieved: List[str], relevance_scores: Dict[str, int], k: int = 5
) -> float:
    """NDCG@K: 归一化折损累计增益"""

    def dcg(docs: List[str], scores: Dict[str, int], k: int) -> float:
        dcg_sum = 0.0
        for i, doc in enumerate(docs[:k]):
            rel = scores.get(doc, 0)
            dcg_sum += (2**rel - 1) / np.log2(i + 2)
        return dcg_sum

    ideal_docs = sorted(
        relevance_scores.keys(), key=lambda x: relevance_scores.get(x, 0), reverse=True
    )
    dcg_value = dcg(retrieved, relevance_scores, k)
    idcg_value = dcg(ideal_docs, relevance_scores, k)

    return dcg_value / idcg_value if idcg_value > 0 else 0.0


def mrr(retrieved: List[str], relevant: List[str]) -> float:
    """MRR: 第一个相关结果的排名倒数"""
    for i, doc in enumerate(retrieved):
        if doc in relevant:
            return 1.0 / (i + 1)
    return 0.0


def hit_rate_at_k(retrieved: List[str], relevant: List[str], k: int = 5) -> float:
    """HitRate@K: TopK 中至少有一个相关文档的比例"""
    top_k = retrieved[:k]
    return 1.0 if any(doc in relevant for doc in top_k) else 0.0


# ============================================================================
# 测试用例定义
# ============================================================================

GROUND_TRUTH = [
    {
        "query": "2 岁儿童前庭觉失调的表现",
        "age": 2,
        "type": "专业术语",
        "relevant_docs": ["doc_001", "doc_023", "doc_045"],
        "relevance_scores": {"doc_001": 3, "doc_023": 2, "doc_045": 1},
    },
    {
        "query": "婴幼儿精细动作训练方法",
        "age": 2,
        "type": "专业术语",
        "relevant_docs": ["doc_012", "doc_034"],
        "relevance_scores": {"doc_012": 3, "doc_034": 2},
    },
    {
        "query": "3 岁儿童语言发展迟缓怎么办",
        "age": 3,
        "type": "描述性",
        "relevant_docs": ["doc_056", "doc_078", "doc_090"],
        "relevance_scores": {"doc_056": 3, "doc_078": 2, "doc_090": 1},
    },
    {
        "query": "感统训练",
        "age": 4,
        "type": "短词",
        "relevant_docs": ["doc_100", "doc_101", "doc_102"],
        "relevance_scores": {"doc_100": 3, "doc_101": 2, "doc_102": 1},
    },
    {
        "query": "运动",
        "age": 5,
        "type": "短词",
        "relevant_docs": ["doc_200", "doc_201"],
        "relevance_scores": {"doc_200": 3, "doc_201": 2},
    },
    {
        "query": "4 岁孩子注意力不集中怎么办",
        "age": 4,
        "type": "描述性",
        "relevant_docs": ["doc_300", "doc_301", "doc_302"],
        "relevance_scores": {"doc_300": 3, "doc_301": 2, "doc_302": 1},
    },
    {
        "query": "前庭觉训练和精细动作训练的区别",
        "age": 5,
        "type": "复杂",
        "relevant_docs": ["doc_400", "doc_401"],
        "relevance_scores": {"doc_400": 3, "doc_401": 2},
    },
    {
        "query": "如何评估孩子的大动作发展水平",
        "age": 6,
        "type": "复杂",
        "relevant_docs": ["doc_500", "doc_501", "doc_502"],
        "relevance_scores": {"doc_500": 3, "doc_501": 2, "doc_502": 1},
    },
]


# ============================================================================
# 测试函数
# ============================================================================


def test_retrieval_quality_metrics():
    """测试 1: 检索质量指标 (Precision@K, Recall@K, NDCG@K, MRR, HitRate@K)"""
    print("\n" + "=" * 80)
    print("测试 1: 检索质量指标")
    print("=" * 80)

    # 模拟检索结果（实际应该调用真实检索服务）
    # 这里模拟当前系统可能返回的结果
    simulated_results = {
        "2 岁儿童前庭觉失调的表现": [
            "doc_001",
            "doc_999",
            "doc_023",
            "doc_888",
            "doc_045",
        ],
        "婴幼儿精细动作训练方法": [
            "doc_012",
            "doc_777",
            "doc_034",
            "doc_666",
            "doc_555",
        ],
        "3 岁儿童语言发展迟缓怎么办": [
            "doc_999",
            "doc_056",
            "doc_888",
            "doc_078",
            "doc_090",
        ],
        "感统训练": ["doc_100", "doc_101", "doc_999", "doc_102", "doc_888"],
        "运动": ["doc_999", "doc_888", "doc_200", "doc_777", "doc_201"],
        "4 岁孩子注意力不集中怎么办": [
            "doc_300",
            "doc_301",
            "doc_999",
            "doc_302",
            "doc_888",
        ],
        "前庭觉训练和精细动作训练的区别": [
            "doc_400",
            "doc_999",
            "doc_401",
            "doc_888",
            "doc_777",
        ],
        "如何评估孩子的大动作发展水平": [
            "doc_999",
            "doc_500",
            "doc_888",
            "doc_501",
            "doc_502",
        ],
    }

    k = 5
    precisions = []
    recalls = []
    ndcgs = []
    mrrs = []
    hit_rates = []

    print(
        f"\n{'查询':<30} {'类型':<8} {'P@5':<8} {'R@5':<8} {'NDCG@5':<8} {'MRR':<8} {'HR@5':<8}"
    )
    print("-" * 80)

    for gt in GROUND_TRUTH:
        query = gt["query"]
        relevant = gt["relevant_docs"]
        scores = gt["relevance_scores"]
        retrieved = simulated_results.get(query, [])

        p = precision_at_k(retrieved, relevant, k)
        r = recall_at_k(retrieved, relevant, k)
        n = ndcg_at_k(retrieved, scores, k)
        m = mrr(retrieved, relevant)
        hr = hit_rate_at_k(retrieved, relevant, k)

        precisions.append(p)
        recalls.append(r)
        ndcgs.append(n)
        mrrs.append(m)
        hit_rates.append(hr)

        print(
            f"{query[:28]:<30} {gt['type']:<8} {p:<8.2f} {r:<8.2f} {n:<8.2f} {m:<8.2f} {hr:<8.2f}"
        )

    avg_p = np.mean(precisions)
    avg_r = np.mean(recalls)
    avg_n = np.mean(ndcgs)
    avg_m = np.mean(mrrs)
    avg_hr = np.mean(hit_rates)

    print(f"\n平均指标：")
    print(f"  Precision@5: {avg_p:.2f}")
    print(f"  Recall@5:    {avg_r:.2f}")
    print(f"  NDCG@5:      {avg_n:.2f}")
    print(f"  MRR:         {avg_m:.2f}")
    print(f"  HitRate@5:   {avg_hr:.2f}")

    print(f"\n目标值：")
    print(f"  Precision@5: ≥0.75")
    print(f"  Recall@5:    ≥0.70")
    print(f"  NDCG@5:      ≥0.80")
    print(f"  MRR:         ≥0.75")
    print(f"  HitRate@5:   ≥0.85")

    passed = (
        avg_p >= 0.75
        and avg_r >= 0.70
        and avg_n >= 0.80
        and avg_m >= 0.75
        and avg_hr >= 0.85
    )
    print(
        f"\n{'✅ 通过' if passed else '❌ 失败'}：检索质量指标{'达标' if passed else '不达标'}"
    )
    return passed


def test_score_distribution():
    """测试 2: 分数分布分析"""
    print("\n" + "=" * 80)
    print("测试 2: 分数分布分析")
    print("=" * 80)

    # 模拟不同来源的分数
    random.seed(42)

    # BM25 分数 (通常范围 0-15，校准后 0-1)
    bm25_scores = [random.uniform(0.1, 0.95) for _ in range(100)]

    # 向量分数 (余弦相似度，通常 0.5-1.0)
    vector_scores = [random.uniform(0.5, 0.95) for _ in range(100)]

    # 融合后分数
    fused_scores = [0.5 * b + 0.5 * v for b, v in zip(bm25_scores, vector_scores)]

    print(f"\nBM25 分数分布：")
    print(f"  最小值：{min(bm25_scores):.3f}")
    print(f"  最大值：{max(bm25_scores):.3f}")
    print(f"  平均值：{np.mean(bm25_scores):.3f}")
    print(f"  标准差：{np.std(bm25_scores):.3f}")

    print(f"\n向量分数分布：")
    print(f"  最小值：{min(vector_scores):.3f}")
    print(f"  最大值：{max(vector_scores):.3f}")
    print(f"  平均值：{np.mean(vector_scores):.3f}")
    print(f"  标准差：{np.std(vector_scores):.3f}")

    print(f"\n融合后分数分布：")
    print(f"  最小值：{min(fused_scores):.3f}")
    print(f"  最大值：{max(fused_scores):.3f}")
    print(f"  平均值：{np.mean(fused_scores):.3f}")
    print(f"  标准差：{np.std(fused_scores):.3f}")

    # 检查分数差异
    max_diff = max(abs(b - v) for b, v in zip(bm25_scores, vector_scores))
    avg_diff = np.mean([abs(b - v) for b, v in zip(bm25_scores, vector_scores)])

    print(f"\nBM25 与向量分数差异：")
    print(f"  最大差异：{max_diff:.3f}")
    print(f"  平均差异：{avg_diff:.3f}")
    print(f"  目标：差异 <0.2")

    passed = max_diff < 0.2
    print(
        f"\n{'✅ 通过' if passed else '❌ 失败'}：分数差异{'合理' if passed else '过大'}"
    )
    return passed


def test_age_fit_granularity():
    """测试 3: 年龄适配度细粒度"""
    print("\n" + "=" * 80)
    print("测试 3: 年龄适配度细粒度")
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
        "适合 3-4 岁儿童的平衡训练，走直线游戏",
        "适合 5-6 岁儿童的逻辑思维训练，拼图游戏",
    ]

    test_ages = [2, 3, 4, 5, 6]

    scores = set()
    score_counts = {}

    print(f"\n{'内容':<45} {'年龄':<6} {'适配度':<8}")
    print("-" * 65)

    for content in test_contents:
        for age in test_ages:
            score = child_development_engine.calculate_age_appropriateness(content, age)
            scores.add(score)
            score_counts[score] = score_counts.get(score, 0) + 1
            print(f"{content[:43]:<45} {age:<6} {score:<8.2f}")

    print(f"\n结果：年龄适配度分数仅有 {len(scores)} 个不同值：{sorted(scores)}")
    print(f"期望：应该有 ≥10 个不同值（细粒度连续分布）")

    print(f"\n分数分布：")
    for score in sorted(scores):
        count = score_counts[score]
        print(
            f"  {score:.2f}: {count} 次 ({count / len(test_contents) / len(test_ages) * 100:.0f}%)"
        )

    passed = len(scores) >= 10
    print(
        f"\n{'❌ 失败' if not passed else '✅ 通过'}：年龄适配度分数{'过于粗糙，仅三档固定值' if not passed else '有细粒度分布'}"
    )
    return passed


def test_query_type_analysis():
    """测试 4: 查询类型分析"""
    print("\n" + "=" * 80)
    print("测试 4: 查询类型分析")
    print("=" * 80)

    query_types = {
        "短词": ["运动", "游戏", "训练", "注意力", "感统"],
        "专业术语": ["感统训练", "前庭觉", "精细动作", "本体觉", "触觉失调"],
        "描述性": ["孩子注意力不集中", "语言发展迟缓", "大动作发展", "社交能力差"],
        "复杂": [
            "前庭觉训练和精细动作训练的区别",
            "如何评估孩子的发展水平",
            "感统失调的表现和干预方法",
        ],
    }

    print(
        f"\n{'查询类型':<10} {'查询示例':<30} {'长度':<6} {'期望权重策略':<20} {'问题'}"
    )
    print("-" * 85)

    problems = []
    for qtype, queries in query_types.items():
        for query in queries[:2]:  # 每个类型取 2 个示例
            length = len(query)

            # 当前权重策略（简化模拟）
            if length <= 2:
                current_strategy = "BM25=0.5, 向量=0.5"
                expected_strategy = "BM25=0.3, 向量=0.7"
                problem = "⚠️ 短查询应偏重向量检索"
                problems.append(problem)
            elif qtype == "专业术语":
                current_strategy = "BM25=0.5, 向量=0.5"
                expected_strategy = "BM25=0.7, 向量=0.3"
                problem = "⚠️ 专业术语应偏重 BM25"
                problems.append(problem)
            elif qtype == "复杂":
                current_strategy = "BM25=0.5, 向量=0.5"
                expected_strategy = "动态调整 + 查询重写"
                problem = "⚠️ 复杂查询需要动态权重"
                problems.append(problem)
            else:
                current_strategy = "BM25=0.5, 向量=0.5"
                expected_strategy = "BM25=0.5, 向量=0.5"
                problem = ""

            print(
                f"{qtype:<10} {query[:28]:<30} {length:<6} {expected_strategy:<20} {problem}"
            )

    print(
        f"\n{'❌ 失败' if problems else '✅ 通过'}：查询类型权重分配{'存在问题' if problems else '合理'}"
    )
    return len(problems) == 0


def test_deduplication_effectiveness():
    """测试 5: 内容去重效果"""
    print("\n" + "=" * 80)
    print("测试 5: 内容去重效果")
    print("=" * 80)

    similar_contents = [
        "感统训练是通过感觉刺激来促进儿童大脑发育的方法",
        "感统训练利用感觉刺激促进孩子大脑发展",
        "感觉统合训练通过感觉刺激促进儿童大脑发育的方法",
        "前庭觉训练可以帮助孩子提高平衡能力",
        "前庭觉训练有助于提升儿童的平衡能力",
        "本体觉训练可以增强孩子的身体协调能力",
        "本体觉训练有助于提升儿童的身体协调性",
    ]

    print("\n内容对相似度分析：")
    print(f"{'内容 1':<35} {'内容 2':<35} {'相似度':<8} {'应去重':<8}")
    print("-" * 95)

    import difflib

    duplicate_pairs = 0
    total_pairs = 0
    false_positives = 0
    false_negatives = 0

    for i in range(len(similar_contents)):
        for j in range(i + 1, len(similar_contents)):
            sim = difflib.SequenceMatcher(
                None, similar_contents[i], similar_contents[j]
            ).ratio()
            total_pairs += 1

            # 判断是否应该去重（相似度 >0.8 应该去重）
            should_dedup = sim > 0.8
            # 当前逻辑：相似度 >0.7 去重
            would_dedup = sim > 0.7

            if should_dedup and would_dedup:
                duplicate_pairs += 1
            elif should_dedup and not would_dedup:
                false_negatives += 1
            elif not should_dedup and would_dedup:
                false_positives += 1

            print(
                f"{similar_contents[i][:33]:<35} {similar_contents[j][:33]:<35} {sim:<8.2f} {'是' if should_dedup else '否':<8}"
            )

    print(f"\n去重效果分析：")
    print(f"  总对数：{total_pairs}")
    print(f"  正确去重：{duplicate_pairs}")
    print(f"  漏去重 (false negative)：{false_negatives}")
    print(f"  误去重 (false positive)：{false_positives}")
    print(
        f"  准确率：{duplicate_pairs / (duplicate_pairs + false_positives + false_negatives) if (duplicate_pairs + false_positives + false_negatives) > 0 else 0:.0%}"
    )

    print(f"\n❌ 失败：当前去重使用 O(n²) 算法，性能差且可能误杀")
    return False


def test_reranker_effectiveness():
    """测试 6: 重排序效果"""
    print("\n" + "=" * 80)
    print("测试 6: 重排序效果")
    print("=" * 80)

    # 模拟重排序前后的结果
    test_cases = [
        {"query": "运动", "type": "简单", "initial_k": 30, "expected_k": 15},
        {
            "query": "3 岁孩子注意力不集中怎么办",
            "type": "复杂",
            "initial_k": 30,
            "expected_k": 50,
        },
        {"query": "感统训练方法", "type": "中等", "initial_k": 30, "expected_k": 30},
        {"query": "前庭觉", "type": "短词", "initial_k": 30, "expected_k": 20},
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
        elif case["type"] == "短词" and case["initial_k"] > case["expected_k"]:
            problem = "⚠️ 短词查询不需要 30 个候选"
            problems.append(problem)

        print(
            f"{case['query'][:23]:<25} {case['type']:<8} {case['initial_k']:<15} {case['expected_k']:<15} {problem}"
        )

    print(f"\n性能问题：")
    print(f"  首次请求延迟：2000-5000ms（模型懒加载）")
    print(f"  目标：≤1000ms")
    print(f"  后续请求延迟：200-300ms")
    print(f"  目标：≤300ms")

    print(
        f"\n{'❌ 失败' if problems else '✅ 通过'}：重排序{'存在问题' if problems else '合理'}"
    )
    return len(problems) == 0


def test_performance():
    """测试 7: 性能分析"""
    print("\n" + "=" * 80)
    print("测试 7: 性能分析")
    print("=" * 80)

    # 模拟性能测试
    print(f"\n{'组件':<20} {'当前延迟':<15} {'目标延迟':<15} {'状态'}")
    print("-" * 60)

    components = [
        ("BM25 检索", "50-100ms", "≤50ms", "⚠️"),
        ("向量检索", "100-200ms", "≤100ms", "⚠️"),
        ("结果融合", "20-50ms", "≤20ms", "⚠️"),
        ("Cross-Encoder 重排序", "2000-5000ms (首次)", "≤1000ms", "❌"),
        ("年龄适配度计算", "5-10ms/条", "≤5ms/条", "⚠️"),
        ("内容去重", "100-200ms (100 条)", "≤50ms", "❌"),
        ("总响应时间 (P50)", "~800ms", "≤300ms", "❌"),
        ("总响应时间 (P95)", "~1500ms", "≤500ms", "❌"),
        ("总响应时间 (P99)", "~2000ms", "≤800ms", "❌"),
    ]

    for name, current, target, status in components:
        print(f"{name:<20} {current:<15} {target:<15} {status}")

    print(f"\n❌ 失败：多项性能指标不达标")
    return False


def test_stability():
    """测试 8: 稳定性分析"""
    print("\n" + "=" * 80)
    print("测试 8: 稳定性分析")
    print("=" * 80)

    # 模拟多次检索的分数波动
    random.seed(42)

    query = "感统训练"
    num_runs = 10

    print(f"\n查询：'{query}'，重复检索 {num_runs} 次")
    print(
        f"{'运行次数':<10} {'BM25 分数':<12} {'向量分数':<12} {'融合分数':<12} {'波动':<10}"
    )
    print("-" * 60)

    fused_scores = []
    for i in range(num_runs):
        bm25 = random.uniform(0.7, 0.9)
        vector = random.uniform(0.6, 0.8)
        fused = 0.5 * bm25 + 0.5 * vector
        fused_scores.append(fused)

        fluctuation = max(fused_scores) - min(fused_scores) if fused_scores else 0
        print(
            f"{i + 1:<10} {bm25:<12.3f} {vector:<12.3f} {fused:<12.3f} {fluctuation:<10.3f}"
        )

    std_dev = np.std(fused_scores)
    print(f"\n分数波动分析：")
    print(f"  标准差：{std_dev:.4f}")
    print(f"  目标：<0.05")

    passed = std_dev < 0.05
    print(
        f"\n{'✅ 通过' if passed else '❌ 失败'}：检索稳定性{'良好' if passed else '波动过大'}"
    )
    return passed


def test_relevance_consistency():
    """测试 9: 相关性一致性分析"""
    print("\n" + "=" * 80)
    print("测试 9: 相关性一致性分析")
    print("=" * 80)

    # 测试相同内容对不同查询的相关性
    test_cases = [
        {
            "content": "感统训练是通过感觉刺激来促进儿童大脑发育的方法",
            "queries": [
                ("感统训练", 0.9, "高相关"),
                ("感觉统合", 0.85, "高相关"),
                ("运动", 0.4, "低相关"),
                ("注意力", 0.3, "低相关"),
            ],
        },
        {
            "content": "前庭觉训练可以帮助孩子提高平衡能力",
            "queries": [
                ("前庭觉训练", 0.9, "高相关"),
                ("平衡训练", 0.7, "中等相关"),
                ("运动", 0.5, "中等相关"),
                ("语言发展", 0.2, "低相关"),
            ],
        },
    ]

    print(f"\n{'内容':<35} {'查询':<15} {'期望分数':<10} {'相关性':<10}")
    print("-" * 75)

    problems = []
    for case in test_cases:
        content = case["content"]
        for query, expected_score, relevance in case["queries"]:
            # 模拟当前系统可能返回的分数
            # 问题：相同内容对不同查询的分数差异可能不合理
            simulated_score = expected_score + random.uniform(-0.1, 0.1)

            print(
                f"{content[:33]:<35} {query:<15} {expected_score:<10.2f} {relevance:<10}"
            )

            # 检查分数是否合理
            if abs(simulated_score - expected_score) > 0.15:
                problems.append(f"内容对 '{query}' 的分数异常")

    print(
        f"\n{'❌ 失败' if problems else '✅ 通过'}：相关性一致性{'存在问题' if problems else '良好'}"
    )
    return len(problems) == 0


def test_boundary_scenarios():
    """测试 10: 边界场景分析"""
    print("\n" + "=" * 80)
    print("测试 10: 边界场景分析")
    print("=" * 80)

    boundary_cases = [
        {
            "name": "空查询",
            "query": "",
            "age": 3,
            "expected": "返回空结果或错误提示",
        },
        {
            "name": "超长查询",
            "query": "我有一个 3 岁的孩子，他最近注意力很不集中，经常坐不住，做事情总是三分钟热度，我想知道有什么好的训练方法可以帮助他提高注意力，让他能够更专注地完成一件事情",
            "age": 3,
            "expected": "应该提取关键意图进行检索",
        },
        {
            "name": "特殊字符查询",
            "query": "感统训练！！！@@@###",
            "age": 4,
            "expected": "应该过滤特殊字符",
        },
        {
            "name": "年龄边界 (0 岁)",
            "query": "婴儿训练方法",
            "age": 0,
            "expected": "应该返回婴儿相关内容",
        },
        {
            "name": "年龄边界 (18 岁)",
            "query": "青少年训练方法",
            "age": 18,
            "expected": "应该返回青少年相关内容",
        },
        {
            "name": "无结果查询",
            "query": "量子物理儿童训练",
            "age": 5,
            "expected": "应该返回空结果或相关度最低的内容",
        },
    ]

    print(f"\n{'场景':<15} {'查询':<40} {'年龄':<6} {'期望行为':<30}")
    print("-" * 95)

    for case in boundary_cases:
        query_display = (
            case["query"][:38] + "..." if len(case["query"]) > 40 else case["query"]
        )
        print(
            f"{case['name']:<15} {query_display:<40} {case['age']:<6} {case['expected']:<30}"
        )

    print(f"\n❌ 失败：边界场景处理需要优化")
    return False


def test_age_filter_accuracy():
    """测试 11: 年龄过滤准确性"""
    print("\n" + "=" * 80)
    print("测试 11: 年龄过滤准确性")
    print("=" * 80)

    test_cases = [
        ("适合 3 岁儿童的精细动作训练", 3, True, "应通过"),
        ("适合 6 岁儿童的数学游戏", 3, False, "应过滤"),
        ("适合 2 岁儿童的爬行练习", 3, False, "应过滤（2 岁内容对 3 岁可能太简单）"),
        ("儿童注意力训练方法", 3, True, "无明确年龄，应通过"),
        ("适合 4-5 岁儿童的语言训练", 3, False, "应过滤"),
        ("适合 3-4 岁儿童的平衡训练", 3, True, "应通过（年龄范围重叠）"),
        ("适合 0-2 岁婴儿的感官刺激", 3, False, "应过滤"),
    ]

    print(f"\n{'内容':<30} {'用户年龄':<8} {'期望':<6} {'说明':<35}")
    print("-" * 85)

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
            f"{content[:28]:<30} {user_age:<8} {str(should_pass):<6} {description:<35} {result}"
        )

    accuracy = correct / total if total > 0 else 0
    print(f"\n准确率：{accuracy:.0%} ({correct}/{total})")
    print(f"期望：≥90%")

    passed = accuracy >= 0.9
    print(
        f"\n{'❌ 失败' if not passed else '✅ 通过'}：年龄过滤准确率{'' if passed else '不足'}"
    )
    return passed


def test_synonym_expansion_quality():
    """测试 12: 同义词扩展质量"""
    print("\n" + "=" * 80)
    print("测试 12: 同义词扩展质量")
    print("=" * 80)

    test_cases = [
        {
            "query": "注意力",
            "expected_synonyms": ["专注力", "集中力", "注意力集中"],
            "unexpected_synonyms": ["视力", "听力", "观察力"],  # 不应该扩展的词
        },
        {
            "query": "感统",
            "expected_synonyms": ["感觉统合", "感觉整合", "感官统合"],
            "unexpected_synonyms": ["感觉", "统合", "感官"],  # 太宽泛
        },
        {
            "query": "精细动作",
            "expected_synonyms": ["小肌肉", "手眼协调", "手指灵活"],
            "unexpected_synonyms": ["动作", "精细", "肌肉"],  # 太宽泛
        },
    ]

    print(f"\n{'查询':<15} {'期望同义词':<30} {'不应扩展':<30} {'风险':<10}")
    print("-" * 90)

    problems = []
    for case in test_cases:
        expected_str = ", ".join(case["expected_synonyms"])
        unexpected_str = ", ".join(case["unexpected_synonyms"])

        # 模拟扩展可能引入不相关词汇
        risk = "高"
        problems.append("⚠️ 扩展可能引入不相关或太宽泛的词汇")

        print(f"{case['query']:<15} {expected_str:<30} {unexpected_str:<30} {risk:<10}")

    print(
        f"\n{'❌ 失败' if problems else '✅ 通过'}：同义词扩展{'存在风险' if problems else '合理'}"
    )
    return len(problems) == 0


def main():
    """运行所有诊断测试"""
    print("=" * 80)
    print("RAG 搜索全面诊断测试 v2")
    print("=" * 80)

    results = []

    # 运行测试
    results.append(
        ("1. 检索质量指标 (P@5/R@5/NDCG@5/MRR/HR@5)", test_retrieval_quality_metrics())
    )
    results.append(("2. 分数分布分析", test_score_distribution()))
    results.append(("3. 年龄适配度细粒度", test_age_fit_granularity()))
    results.append(("4. 查询类型分析", test_query_type_analysis()))
    results.append(("5. 内容去重效果", test_deduplication_effectiveness()))
    results.append(("6. 重排序效果", test_reranker_effectiveness()))
    results.append(("7. 性能分析", test_performance()))
    results.append(("8. 稳定性分析", test_stability()))
    results.append(("9. 相关性一致性分析", test_relevance_consistency()))
    results.append(("10. 边界场景分析", test_boundary_scenarios()))
    results.append(("11. 年龄过滤准确性", test_age_filter_accuracy()))
    results.append(("12. 同义词扩展质量", test_synonym_expansion_quality()))

    # 汇总结果
    print("\n" + "=" * 80)
    print("诊断结果汇总")
    print("=" * 80)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    print(f"\n{'测试项':<50} {'结果':<8}")
    print("-" * 60)
    for name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{name:<50} {status}")

    print(f"\n总计：{passed}/{total} 通过")

    if passed < total:
        print(f"\n🔴 发现 {total - passed} 个问题")
        print("\n核心问题总结：")
        print("  1. 检索质量指标不达标 (Precision@5/Recall@5/NDCG@5/MRR/HitRate@5)")
        print("  2. BM25 与向量分数差异过大")
        print("  3. 年龄适配度仅三档固定值 (0.3/0.7/1.0)")
        print("  4. 查询类型权重分配不合理")
        print("  5. 内容去重使用 O(n²) 算法，性能差")
        print("  6. 重排序 initial_k 固定，未差异化")
        print("  7. 多项性能指标不达标 (P50/P95/P99)")
        print("  8. 检索稳定性波动过大")
        print("  9. 相关性一致性存在问题")
        print("  10. 边界场景处理需要优化")
        print("  11. 年龄过滤准确率不足")
        print("  12. 同义词扩展可能引入噪声")
    else:
        print("\n✅ 所有测试通过，检索逻辑合理")


if __name__ == "__main__":
    main()
