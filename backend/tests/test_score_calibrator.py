"""分数校准器单元测试"""

import pytest
import math
from src.core.rag.score_calibrator import ScoreCalibrator

# 诊断测试中的实际分数数据（模拟）
DIAGNOSTIC_BM25_SCORES = [0.106, 0.234, 0.456, 0.678, 0.948]
DIAGNOSTIC_VECTOR_SCORES = [0.500, 0.620, 0.710, 0.830, 0.950]


@pytest.fixture
def calibrator():
    return ScoreCalibrator(sigmoid_midpoint=0.5, sigmoid_steepness=10.0)


class TestMinMaxNormalize:
    """Min-Max 归一化测试"""

    def test_normal_case(self, calibrator):
        """正常场景：不同分数"""
        scores = [10.0, 20.0, 30.0, 40.0, 50.0]
        normalized = calibrator._min_max_normalize(scores)

        assert normalized[0] == pytest.approx(0.0)  # 最小值 → 0
        assert normalized[-1] == pytest.approx(1.0)  # 最大值 → 1
        assert normalized[2] == pytest.approx(0.5)  # 中间值 → 0.5

    def test_all_same_scores(self, calibrator):
        """边界场景：所有分数相同"""
        scores = [0.5, 0.5, 0.5]
        normalized = calibrator._min_max_normalize(scores)

        assert all(n == 0.5 for n in normalized)

    def test_empty_list(self, calibrator):
        """边界场景：空列表"""
        assert calibrator._min_max_normalize([]) == []

    def test_single_score(self, calibrator):
        """边界场景：单个分数（min_samples=1 时进行归一化）"""
        assert calibrator._min_max_normalize([0.7], min_samples=1) == [0.5]

    def test_negative_scores(self, calibrator):
        """边界场景：负数分数（BM25 可能为负）"""
        scores = [-5.0, 0.0, 5.0]
        normalized = calibrator._min_max_normalize(scores)

        assert normalized[0] == pytest.approx(0.0)
        assert normalized[1] == pytest.approx(0.5)
        assert normalized[2] == pytest.approx(1.0)

    def test_insufficient_samples_no_normalize(self, calibrator):
        """样本数不足时不进行归一化，返回原始分数"""
        # 2 个样本 (< min_samples=3)
        scores = [0.1, 0.9]
        normalized = calibrator._min_max_normalize(scores, min_samples=3)

        # 应返回原始分数（不归一化）
        assert normalized == scores, f"样本数不足时应返回原始分数，实际: {normalized}"

    def test_single_score_no_normalize(self, calibrator):
        """单个样本时不进行归一化"""
        scores = [0.7]
        normalized = calibrator._min_max_normalize(scores, min_samples=3)

        assert normalized == scores, "单个样本时，应返回原始分数"

    def test_two_scores_no_normalize(self, calibrator):
        """两个样本时不进行归一化"""
        scores = [0.3, 0.8]
        normalized = calibrator._min_max_normalize(scores, min_samples=3)

        assert normalized == scores, "两个样本时，应返回原始分数"

    def test_three_scores_normalize(self, calibrator):
        """三个样本时进行归一化"""
        scores = [0.1, 0.5, 0.9]
        normalized = calibrator._min_max_normalize(scores, min_samples=3)

        assert normalized[0] == pytest.approx(0.0)
        assert normalized[1] == pytest.approx(0.5)
        assert normalized[2] == pytest.approx(1.0)

    def test_custom_min_samples_threshold(self, calibrator):
        """自定义最小样本数阈值"""
        scores = [0.2, 0.4, 0.6, 0.8]

        # min_samples=5，4 个样本不足
        normalized = calibrator._min_max_normalize(scores, min_samples=5)
        assert normalized == scores

        # min_samples=3，4 个样本足够
        normalized = calibrator._min_max_normalize(scores, min_samples=3)
        assert normalized != scores  # 应进行归一化


class TestSigmoidCalibration:
    """Sigmoid 校准测试"""

    def test_output_range(self, calibrator):
        """验证输出在 [0, 1] 范围内"""
        for score in [0.0, 0.1, 0.3, 0.5, 0.7, 0.9, 1.0]:
            result = calibrator._sigmoid(score)
            assert 0.0 < result < 1.0, f"score={score}, result={result} 超出 (0,1)"

    def test_midpoint(self, calibrator):
        """验证中点分数为 0.5 时输出 0.5"""
        result = calibrator._sigmoid(0.5)
        assert result == pytest.approx(0.5, abs=0.001)

    def test_monotonicity(self, calibrator):
        """验证单调递增：输入越大，输出越大"""
        scores = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]
        results = [calibrator._sigmoid(s) for s in scores]

        for i in range(len(results) - 1):
            assert results[i] < results[i + 1], (
                f"非单调：{results[i]} >= {results[i + 1]}"
            )

    def test_steepness_effect(self):
        """验证 steepness 参数对区分度的影响"""
        calibrator_steep = ScoreCalibrator(sigmoid_steepness=20.0)
        calibrator_flat = ScoreCalibrator(sigmoid_steepness=5.0)

        # 高分和低分的差异
        high_steep = calibrator_steep._sigmoid(0.8) - calibrator_steep._sigmoid(0.2)
        high_flat = calibrator_flat._sigmoid(0.8) - calibrator_flat._sigmoid(0.2)

        assert high_steep > high_flat, "steepness 越大，区分度应越高"


class TestScoreDifference:
    """分数差异测试"""

    def test_diagnostic_data_difference(self, calibrator):
        """使用诊断测试数据验证最大差异 <0.2"""
        bm25_calibrated = calibrator.calibrate_scores(DIAGNOSTIC_BM25_SCORES)
        vector_calibrated = calibrator.calibrate_scores(DIAGNOSTIC_VECTOR_SCORES)

        # 计算对应位置的差异
        diffs = [
            abs(bm25_calibrated[i] - vector_calibrated[i])
            for i in range(min(len(bm25_calibrated), len(vector_calibrated)))
        ]

        max_diff = max(diffs)
        avg_diff = sum(diffs) / len(diffs)

        assert max_diff < 0.2, f"最大差异 {max_diff:.4f} >= 0.2"
        assert avg_diff < 0.15, f"平均差异 {avg_diff:.4f} >= 0.15"

    def test_extreme_case_difference(self, calibrator):
        """极端场景：BM25 和向量分数范围差异很大"""
        # BM25 范围 [0.1, 0.9]，向量范围 [0.5, 0.95]
        bm25 = [0.1, 0.3, 0.5, 0.7, 0.9]
        vector = [0.5, 0.6, 0.7, 0.8, 0.95]

        bm25_cal = calibrator.calibrate_scores(bm25)
        vector_cal = calibrator.calibrate_scores(vector)

        diffs = [abs(bm25_cal[i] - vector_cal[i]) for i in range(5)]
        max_diff = max(diffs)

        assert max_diff < 0.2, f"极端场景最大差异 {max_diff:.4f} >= 0.2"

    def test_calibrate_and_compare_method(self, calibrator):
        """验证 calibrate_and_compare 方法返回正确统计信息"""
        result = calibrator.calibrate_and_compare(
            DIAGNOSTIC_BM25_SCORES, DIAGNOSTIC_VECTOR_SCORES
        )

        assert "max_diff" in result
        assert "avg_diff" in result
        assert "bm25_range" in result
        assert "vector_range" in result
        assert result["max_diff"] < 0.2


class TestMergeOrderPreservation:
    """融合排序测试"""

    def test_high_score_stays_high(self, calibrator):
        """验证高分节点融合后仍排在前面"""
        # 构造节点：BM25 和向量分数都高的节点
        bm25_scores = [0.9, 0.5, 0.1]
        vector_scores = [0.9, 0.5, 0.1]

        merged_scores = calibrator.calibrate_and_merge(
            bm25_scores, vector_scores, bm25_weight=0.5, vector_weight=0.5
        )

        # 验证融合后分数保持顺序
        assert merged_scores[0] > merged_scores[1] > merged_scores[2]

    def test_mixed_sources_order(self, calibrator):
        """验证混合来源（BM25 独有、向量独有、两者共有）节点排序正确"""
        # BM25 独有高分节点
        bm25_scores = [0.9, 0.3]
        # 向量独有高分节点
        vector_scores = [0.85, 0.2]

        merged = calibrator.calibrate_and_merge(
            bm25_scores, vector_scores, bm25_weight=0.5, vector_weight=0.5
        )

        # 验证高分节点排在前面
        assert merged[0] > merged[1]


class TestSteepnessParameter:
    """steepness 参数测试"""

    def test_low_steepness(self):
        """低 steepness：分数区分度低，分布平缓"""
        calibrator = ScoreCalibrator(sigmoid_steepness=5.0)
        scores = [0.2, 0.4, 0.6, 0.8]
        calibrated = calibrator.calibrate_scores(scores)

        # 分数差异较小
        diff = calibrated[-1] - calibrated[0]
        assert diff < 0.95, f"低 steepness 区分度过高：{diff:.4f}"

    def test_medium_steepness(self):
        """中等 steepness：平衡区分度和稳定性"""
        calibrator = ScoreCalibrator(sigmoid_steepness=10.0)
        scores = [0.2, 0.4, 0.6, 0.8]
        calibrated = calibrator.calibrate_scores(scores)

        diff = calibrated[-1] - calibrated[0]
        assert 0.5 <= diff <= 1.0, f"中等 steepness 区分度异常：{diff:.4f}"

    def test_high_steepness(self):
        """高 steepness：分数区分度高，接近二值化"""
        calibrator = ScoreCalibrator(sigmoid_steepness=20.0)
        scores = [0.2, 0.4, 0.6, 0.8]
        calibrated = calibrator.calibrate_scores(scores)

        diff = calibrated[-1] - calibrated[0]
        assert diff > 0.8, f"高 steepness 区分度过低：{diff:.4f}"

    @pytest.mark.parametrize("steepness", [5.0, 10.0, 15.0, 20.0])
    def test_output_range_independent_of_steepness(self, steepness):
        """验证无论 steepness 如何，输出都在 (0, 1) 范围内"""
        calibrator = ScoreCalibrator(sigmoid_steepness=steepness)
        for score in [0.0, 0.25, 0.5, 0.75, 1.0]:
            result = calibrator._sigmoid(score)
            assert 0.0 < result < 1.0
