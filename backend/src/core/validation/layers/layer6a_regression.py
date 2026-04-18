"""Layer 6a: 回归检测"""

import logging
from typing import Any

from sqlalchemy import select

from src.models.rag_eval.test_run import RagEvalTestRun

logger = logging.getLogger(__name__)


class Layer6aRegressionDetection:
    """Layer 6a: 回归检测"""

    def __init__(self, session_factory, test_run):
        self.session_factory = session_factory
        self.test_run = test_run

    async def execute(self) -> dict:
        """执行回归检测"""
        async with self.session_factory() as session:
            previous_run = await self._get_previous_run(session)

        if not previous_run:
            return {"status": "skipped", "data": {"reason": "不存在上一次运行记录"}}

        current_metrics = {
            "p_at_5": self.test_run.overall_precision or 0,
            "r_at_5": self.test_run.overall_recall or 0,
            "f1": self.test_run.overall_f1 or 0,
            "mrr": self.test_run.overall_mrr or 0,
        }
        previous_metrics = {
            "p_at_5": previous_run.overall_precision or 0,
            "r_at_5": previous_run.overall_recall or 0,
            "f1": previous_run.overall_f1 or 0,
            "mrr": previous_run.overall_mrr or 0,
        }

        regressed_metrics = []

        for key, current_val in current_metrics.items():
            if key in previous_metrics:
                prev_val = previous_metrics[key]
                if prev_val == 0:
                    continue

                delta = (current_val - prev_val) / prev_val

                if delta < -0.15:
                    severity = "critical"
                elif delta < -0.05:
                    severity = "warning"
                else:
                    continue

                regressed_metrics.append(
                    {
                        "metric": key,
                        "current_value": current_val,
                        "previous_value": prev_val,
                        "delta_percent": round(delta * 100, 2),
                        "severity": severity,
                    }
                )

        warnings = []
        for m in regressed_metrics:
            level = "critical" if m["severity"] == "critical" else "warning"
            warnings.append(
                {
                    "level": level,
                    "message": f"{m['metric']} 退化 {abs(m['delta_percent'])}% ({m['current_value']:.2f} vs {m['previous_value']:.2f})",
                }
            )

        return {
            "status": "completed",
            "data": {
                "regressed_metrics": regressed_metrics,
                "previous_run_id": previous_run.id,
                "warnings": warnings,
            },
        }

    async def _get_previous_run(self, session):
        """获取上一次运行记录"""
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
