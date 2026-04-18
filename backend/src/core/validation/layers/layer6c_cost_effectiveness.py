"""Layer 6c: 成本效果分析"""

import logging
import math
from typing import Any

from sqlalchemy import select

from src.models.rag_eval.test_run import RagEvalTestRun

logger = logging.getLogger(__name__)

METRIC_WEIGHTS = {
    "p_at_5": 30,
    "r_at_5": 30,
    "f1": 20,
    "mrr": 10,
    "ndcg": 10,
}


class Layer6cCostEffectiveness:
    """Layer 6c: 成本效果分析"""

    def __init__(self, session_factory, test_run):
        self.session_factory = session_factory
        self.test_run = test_run

    async def execute(self) -> dict:
        """执行成本效果分析"""
        async with self.session_factory() as session:
            previous_run = await self._get_previous_run(session)

        if not previous_run:
            return {"status": "skipped", "data": {"reason": "不存在上一次运行记录"}}

        config_changed = (
            self.test_run.config_version_id != previous_run.config_version_id
        )

        if not config_changed:
            return {"status": "skipped", "data": {"reason": "配置未变更"}}

        current_metrics = {
            "p_at_5": self.test_run.overall_precision or 0,
            "r_at_5": self.test_run.overall_recall or 0,
            "f1": self.test_run.overall_f1 or 0,
            "mrr": self.test_run.overall_mrr or 0,
            "ndcg": self.test_run.overall_ndcg or 0,
        }
        previous_metrics = {
            "p_at_5": previous_run.overall_precision or 0,
            "r_at_5": previous_run.overall_recall or 0,
            "f1": previous_run.overall_f1 or 0,
            "mrr": previous_run.overall_mrr or 0,
            "ndcg": previous_run.overall_ndcg or 0,
        }

        metric_improvement_score = self._calc_metric_improvement_score(
            previous_metrics, current_metrics
        )

        extra_tokens = self._estimate_extra_tokens(previous_run, self.test_run)
        extra_cost_score = self._calc_extra_cost_score(extra_tokens)

        if extra_tokens == 0:
            cost_effectiveness_ratio = metric_improvement_score * 10
        else:
            cost_effectiveness_ratio = (
                metric_improvement_score / extra_cost_score
                if extra_cost_score > 0
                else 0
            )

        recommendation = self._get_recommendation(cost_effectiveness_ratio)

        return {
            "status": "completed",
            "data": {
                "metric_improvement_score": round(metric_improvement_score, 2),
                "extra_tokens": extra_tokens,
                "extra_cost_score": round(extra_cost_score, 2),
                "cost_effectiveness_ratio": round(cost_effectiveness_ratio, 2),
                "recommendation": recommendation,
                "config_changes": self._extract_config_changes(previous_run, session),
            },
        }

    def _calc_metric_improvement_score(self, prev: dict, curr: dict) -> float:
        """指标提升得分"""
        score = 0
        for metric, weight in METRIC_WEIGHTS.items():
            delta = curr.get(metric, 0) - prev.get(metric, 0)
            score += delta * weight
        return max(0, score)

    def _estimate_extra_tokens(
        self, prev_run: RagEvalTestRun, curr_run: RagEvalTestRun
    ) -> int:
        """估算额外 token 消耗（当前无 total_tokens 字段，使用 0 占位）"""
        return 0

    def _calc_extra_cost_score(self, extra_tokens: int) -> float:
        """额外成本得分"""
        return math.log2(1 + extra_tokens / 1000)

    def _get_recommendation(self, ratio: float) -> str:
        """获取建议"""
        if ratio < 0.1:
            return "不建议应用该变更 (成本高，提升小)"
        elif ratio <= 0.5:
            return "可考虑应用 (权衡成本与效果)"
        else:
            return "强烈推荐应用 (成本低，提升大)"

    async def _get_previous_run(self, session):
        """获取上一次运行"""
        stmt = (
            select(RagEvalTestRun)
            .where(RagEvalTestRun.test_set_id == self.test_run.test_set_id)
            .where(RagEvalTestRun.id != self.test_run.id)
            .where(RagEvalTestRun.status == "completed")
            .order_by(RagEvalTestRun.created_at.desc())
            .limit(1)
        )
        result = await session.execute(stmt)
        return result.scalars().first()

    def _extract_config_changes(self, previous_run: RagEvalTestRun, session) -> list:
        """提取配置变更（从 ConfigVersion 的 config_snapshot 比较）"""
        prev_config = {}
        curr_config = {}

        if previous_run.config_version:
            prev_config = previous_run.config_version.config_snapshot or {}
        if self.test_run.config_version:
            curr_config = self.test_run.config_version.config_snapshot or {}

        changes = []
        all_keys = set(prev_config.keys()) | set(curr_config.keys())
        for key in all_keys:
            old_val = prev_config.get(key)
            new_val = curr_config.get(key)
            if old_val != new_val:
                changes.append(
                    {
                        "key": key,
                        "old_value": old_val,
                        "new_value": new_val,
                    }
                )
        return changes
