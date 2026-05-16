"""L1 检索排名计算器——MRR、NDCG"""

import math

from src.schemas.rag_eval.metrics import MetricInput, MetricOutput
from src.service.rag_eval.metrics.scoring.base import MetricCalculator


class MRR(MetricCalculator):
    """平均倒数排名（Mean Reciprocal Rank）

    计算: 1 / 第一个相关结果的排名
    阈值: >= 0.5
    """

    @property
    def name(self) -> str:
        return "mrr"

    @property
    def layer(self) -> int:
        return 1

    @property
    def description(self) -> str:
        return "平均倒数排名：第一个相关结果出现位置的倒数"

    async def calculate(self, input_data: MetricInput) -> MetricOutput:
        threshold = await self._get_threshold()
        expected = set(input_data.expected_knowledge_ids)
        actual = input_data.actual_knowledge_ids or input_data.retrieved_contexts
        actual_list = list(actual) if actual else []

        if not actual_list:
            return MetricOutput(score=0.0, passed=False, threshold=threshold, details={"reason": "无检索结果"})

        first_rank = 0
        for i, doc_id in enumerate(actual_list, start=1):
            if doc_id in expected:
                first_rank = i
                break

        score = 1.0 / first_rank if first_rank > 0 else 0.0
        return MetricOutput(
            score=round(score, 4),
            passed=score >= threshold,
            threshold=threshold,
            details={"first_rank": first_rank, "total_retrieved": len(actual_list)},
        )


class NDCG(MetricCalculator):
    """归一化折损累积增益（Normalized Discounted Cumulative Gain）

    计算: DCG / ideal_DCG
    DCG = sum(rel_i / log2(i+1)) for i in 1..k
    阈值: >= 0.6
    """

    @property
    def name(self) -> str:
        return "ndcg"

    @property
    def layer(self) -> int:
        return 1

    @property
    def description(self) -> str:
        return "归一化折损累积增益：考虑排名位置的检索质量指标"

    async def calculate(self, input_data: MetricInput) -> MetricOutput:
        threshold = await self._get_threshold()
        expected = set(input_data.expected_knowledge_ids)
        actual = input_data.actual_knowledge_ids or input_data.retrieved_contexts
        actual_list = list(actual) if actual else []

        if not actual_list or not expected:
            return MetricOutput(score=0.0, passed=False, threshold=threshold, details={"reason": "无检索结果或无期望知识片段"})

        # 二元相关性：相关=1，无关=0
        relevance = [1.0 if doc_id in expected else 0.0 for doc_id in actual_list]

        dcg = sum(rel / math.log2(i + 2) for i, rel in enumerate(relevance))

        # ideal DCG：取前 k 个位置全部相关
        ideal_k = min(len(expected), len(actual_list))
        ideal_relevance = [1.0] * ideal_k
        ideal_dcg = sum(rel / math.log2(i + 2) for i, rel in enumerate(ideal_relevance))

        score = dcg / ideal_dcg if ideal_dcg > 0 else 0.0
        return MetricOutput(
            score=round(min(score, 1.0), 4),
            passed=score >= threshold,
            threshold=threshold,
            details={"dcg": round(dcg, 4), "ideal_dcg": round(ideal_dcg, 4), "relevant_count": sum(relevance)},
        )
