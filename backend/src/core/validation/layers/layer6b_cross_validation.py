"""Layer 6b: 交叉验证"""

import logging
import math
from collections import defaultdict
from typing import Any

import numpy as np
from sqlalchemy import select

from src.models.rag_eval.test_case import RagEvalTestCase
from src.models.rag_eval.test_run_result import RagEvalTestRunResult

logger = logging.getLogger(__name__)


class Layer6bCrossValidation:
    """Layer 6b: 交叉验证"""

    def __init__(self, session_factory, test_run):
        self.session_factory = session_factory
        self.test_run = test_run

    async def execute(self) -> dict:
        """执行交叉验证"""
        async with self.session_factory() as session:
            stmt = (
                select(RagEvalTestRunResult, RagEvalTestCase)
                .join(
                    RagEvalTestCase, RagEvalTestRunResult.case_id == RagEvalTestCase.id
                )
                .where(RagEvalTestRunResult.run_id == self.test_run.id)
            )
            result = await session.execute(stmt)
            rows = result.all()

        if not rows:
            return {"status": "skipped", "data": {"reason": "缺少测试结果"}}

        by_domain = defaultdict(list)
        by_age_group = defaultdict(list)

        for test_result, test_case in rows:
            domain = test_case.domain.value if test_case.domain else "unknown"
            age_months = test_case.age_months
            if age_months is None:
                age_group = "unknown"
            elif age_months <= 12:
                age_group = "0-12月"
            elif age_months <= 36:
                age_group = "13-36月"
            elif age_months <= 72:
                age_group = "37-72月"
            else:
                age_group = "72月+"

            # 从 hit_at_1/3/5 计算近似 F1
            hit_count = sum(
                [test_result.hit_at_1, test_result.hit_at_3, test_result.hit_at_5]
            )
            f1 = hit_count / 3.0

            by_domain[domain].append(f1)
            by_age_group[age_group].append(f1)

        domain_metrics = {k: float(np.mean(v)) for k, v in by_domain.items()}
        age_group_metrics = {k: float(np.mean(v)) for k, v in by_age_group.items()}

        avg_f1 = float(np.mean(list(domain_metrics.values()))) if domain_metrics else 0

        underperforming_domains = []
        for domain, f1 in domain_metrics.items():
            if f1 < avg_f1 - 0.1:
                underperforming_domains.append(
                    {
                        "domain": domain,
                        "f1": round(f1, 3),
                        "delta_from_avg": round(f1 - avg_f1, 3),
                    }
                )

        consistency_score = self._calc_consistency_score(
            domain_metrics, age_group_metrics
        )

        warnings = []
        if underperforming_domains:
            for d in underperforming_domains:
                warnings.append(
                    {
                        "level": "warning",
                        "message": f"领域 '{d['domain']}' F1 ({d['f1']:.2f}) 显著低于平均 ({avg_f1:.2f})",
                    }
                )

        if consistency_score < 0.7:
            warnings.append(
                {
                    "level": "warning",
                    "message": f"整体一致性差 ({consistency_score:.2f} < 0.7)",
                }
            )

        return {
            "status": "completed",
            "data": {
                "domain_metrics": domain_metrics,
                "age_group_metrics": age_group_metrics,
                "avg_f1": round(avg_f1, 3),
                "underperforming_domains": underperforming_domains,
                "consistency_score": round(consistency_score, 3),
                "warnings": warnings,
            },
        }

    def _calc_consistency_score(
        self, domain_metrics: dict, age_group_metrics: dict
    ) -> float:
        """计算一致性评分（基于组间方差占比，值域 [0, 1]）"""
        all_metrics = list(domain_metrics.values()) + list(age_group_metrics.values())
        if len(all_metrics) < 2:
            return 1.0

        mean = np.mean(all_metrics)
        if mean == 0:
            return 0

        std = np.std(all_metrics)
        cv = std / mean

        # 使用指数衰减映射，CV 越大一致性越差，但不会直接归零
        return math.exp(-cv * 2)
