"""Layer 6d: A/B 影子测试"""

import logging
import numpy as np
from typing import Any
from scipy import stats

from sqlalchemy import select
from src.models.rag_eval.test_run import RagEvalTestRun
from src.models.rag_eval.test_run_result import RagEvalTestRunResult
from src.models.rag_eval.enums import RagEvalABTestSide

logger = logging.getLogger(__name__)


class Layer6dABShadowTest:
    """Layer 6d: A/B 影子测试"""

    def __init__(self, session_factory, test_run):
        self.session_factory = session_factory
        self.test_run = test_run

    async def execute(self) -> dict:
        """执行 A/B 对比"""
        if not self.test_run.ab_test_id:
            return {"status": "skipped", "data": {"reason": "无 A/B 测试标识"}}

        async with self.session_factory() as session:
            # 查询同一 ab_test_id 下的 A 和 B 两组运行
            stmt = (
                select(RagEvalTestRun)
                .where(RagEvalTestRun.ab_test_id == self.test_run.ab_test_id)
                .where(RagEvalTestRun.status == "completed")
            )
            result = await session.execute(stmt)
            all_runs = result.scalars().all()

        runs_a = [r for r in all_runs if r.ab_test_side == RagEvalABTestSide.A]
        runs_b = [r for r in all_runs if r.ab_test_side == RagEvalABTestSide.B]

        if not runs_a or not runs_b:
            return {"status": "skipped", "data": {"reason": "缺少 A 或 B 侧运行数据"}}

        # 获取 A 和 B 的运行结果
        run_ids_a = [r.id for r in runs_a]
        run_ids_b = [r.id for r in runs_b]

        async with self.session_factory() as session:
            stmt_results = select(RagEvalTestRunResult).where(
                RagEvalTestRunResult.run_id.in_(run_ids_a + run_ids_b)
            )
            result = await session.execute(stmt_results)
            all_results = result.scalars().all()

        results_a = [r for r in all_results if r.run_id in run_ids_a]
        results_b = [r for r in all_results if r.run_id in run_ids_b]

        paired_metrics = self._pair_results(results_a, results_b)

        if not paired_metrics:
            return {"status": "failed", "data": {"reason": "无法配对结果"}}

        metric_deltas = self._calc_metric_deltas(paired_metrics)

        p_value, confidence_interval = self._paired_t_test(paired_metrics)

        # f1_delta = mean(B) - mean(A)，delta > 0 说明 B 更好
        winner = "B" if metric_deltas.get("f1_delta", 0) > 0 else "A"
        if p_value >= 0.05:
            conclusion = "差异不显著，A/B 配置效果相当"
        else:
            conclusion = f"配置 {winner} 胜出 (p={p_value:.3f})"

        return {
            "status": "completed",
            "data": {
                "winner": winner if p_value < 0.05 else "tie",
                "conclusion": conclusion,
                "metric_deltas": metric_deltas,
                "p_value": round(p_value, 4),
                "confidence_interval": [round(ci, 4) for ci in confidence_interval],
                "per_case_comparison": paired_metrics[:20],
            },
        }

    def _pair_results(self, results_a: list, results_b: list) -> list:
        """配对结果（基于 query）"""
        by_query_a = {}
        for r in results_a:
            q = r.query or ""
            if q not in by_query_a:
                by_query_a[q] = r

        by_query_b = {}
        for r in results_b:
            q = r.query or ""
            if q not in by_query_b:
                by_query_b[q] = r

        paired = []
        for query in by_query_a:
            if not query or query not in by_query_b:
                continue
            ra = by_query_a[query]
            rb = by_query_b[query]

            # 从 hit_at_1/3/5 计算近似 F1
            hit_count_a = sum([ra.hit_at_1, ra.hit_at_3, ra.hit_at_5])
            f1_a = hit_count_a / 3.0
            hit_count_b = sum([rb.hit_at_1, rb.hit_at_3, rb.hit_at_5])
            f1_b = hit_count_b / 3.0

            paired.append(
                {
                    "query": query,
                    "hit_at_1_a": int(ra.hit_at_1),
                    "hit_at_3_a": int(ra.hit_at_3),
                    "hit_at_5_a": int(ra.hit_at_5),
                    "f1_a": f1_a,
                    "hit_at_1_b": int(rb.hit_at_1),
                    "hit_at_3_b": int(rb.hit_at_3),
                    "hit_at_5_b": int(rb.hit_at_5),
                    "f1_b": f1_b,
                }
            )
        return paired

    def _calc_metric_deltas(self, paired: list) -> dict:
        """计算指标差异"""
        if not paired:
            return {}

        deltas = {}
        for metric_key in [
            "hit_at_1",
            "hit_at_3",
            "hit_at_5",
            "f1",
        ]:
            values_a = [p.get(f"{metric_key}_a", 0) for p in paired]
            values_b = [p.get(f"{metric_key}_b", 0) for p in paired]
            deltas[f"{metric_key}_delta"] = round(
                float(np.mean(values_b) - np.mean(values_a)), 4
            )

        return deltas

    def _paired_t_test(self, paired: list) -> tuple:
        """配对 t-test"""
        if len(paired) < 2:
            return 1.0, (0, 0)

        values_a = [p["hit_at_5_a"] for p in paired]
        values_b = [p["hit_at_5_b"] for p in paired]

        t_stat, p_value = stats.ttest_rel(values_b, values_a)

        diff = np.array(values_b) - np.array(values_a)
        sem_val = stats.sem(diff)
        if sem_val == 0:
            ci = (float(np.mean(diff)), float(np.mean(diff)))
        else:
            ci = stats.t.interval(0.95, len(diff) - 1, loc=np.mean(diff), scale=sem_val)

        return p_value, ci
