"""Layer 6 四子层执行器（用户手动触发）"""

import asyncio
import logging
from typing import Any

from src.core.validation.layers.layer6a_regression import \
    Layer6aRegressionDetection
from src.core.validation.layers.layer6b_cross_validation import \
    Layer6bCrossValidation
from src.core.validation.layers.layer6c_cost_effectiveness import \
    Layer6cCostEffectiveness
from src.core.validation.layers.layer6d_ab_test import Layer6dABShadowTest

logger = logging.getLogger(__name__)


class Layer6Runner:
    """Layer 6 四子层执行器（用户手动触发）"""

    def __init__(self, session_factory, test_run):
        self.session_factory = session_factory
        self.test_run = test_run

    async def execute(self) -> dict:
        """执行 Layer 6 全部四子层，返回聚合结果"""
        layer6_results = {}

        # 四个子层依次执行
        sublayers = [
            (
                "regression",
                Layer6aRegressionDetection(self.session_factory, self.test_run),
            ),
            (
                "cross_validation",
                Layer6bCrossValidation(self.session_factory, self.test_run),
            ),
            (
                "cost_effectiveness",
                Layer6cCostEffectiveness(self.session_factory, self.test_run),
            ),
            (
                "ab_shadow_test",
                Layer6dABShadowTest(self.session_factory, self.test_run),
            ),
        ]

        for key, layer in sublayers:
            try:
                result = await asyncio.wait_for(layer.execute(), timeout=60)
                layer6_results[key] = result
            except asyncio.TimeoutError:
                logger.warning(f"Layer 6 {key} 超时 (60s)")
                layer6_results[key] = {
                    "status": "timeout",
                    "data": {"reason": "超时 (60s)"},
                }
            except Exception as e:
                logger.error(f"Layer 6 {key} 异常: {e}")
                layer6_results[key] = {
                    "status": "degraded",
                    "data": {"reason": str(e)},
                }

        # 聚合 Layer 6 状态
        statuses = [
            r.get("status", "completed")
            for r in layer6_results.values()
            if isinstance(r, dict)
        ]
        priority = {"degraded": 0, "timeout": 1, "skipped": 2, "completed": 3}
        worst = (
            min(statuses, key=lambda s: priority.get(s, 3)) if statuses else "completed"
        )

        return {
            "status": worst,
            "data": layer6_results,
        }
