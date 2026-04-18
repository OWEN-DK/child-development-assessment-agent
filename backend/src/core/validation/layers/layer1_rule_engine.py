import logging
from typing import Any

from src.core.validation.config import get_config_value

logger = logging.getLogger(__name__)

_DEFAULT_PARAM_SAFE_RANGES = {
    "bm25_top_k": {"min": 5, "max": 50, "recommended": [10, 20], "step": 5},
    "vector_top_k": {"min": 5, "max": 50, "recommended": [10, 20], "step": 5},
    "fusion_threshold": {
        "min": 0.1,
        "max": 0.5,
        "recommended": [0.2, 0.3],
        "step": 0.05,
    },
    "reranker_initial_k": {"min": 10, "max": 100, "recommended": [20, 50], "step": 10},
    "reranker_final_k": {"min": 1, "max": 20, "recommended": [3, 10], "step": 2},
    "age_filter_strictness": {
        "min": 0.0,
        "max": 1.0,
        "recommended": [0.3, 0.7],
        "step": 0.1,
    },
    "chunk_size": {"min": 256, "max": 2048, "recommended": [512, 1024], "step": 128},
}

_DEFAULT_THRESHOLDS = {
    "p_at_5": 0.70,
    "r_at_5": 0.85,
    "f1": 0.75,
    "mrr": 0.70,
    "short_query_failure_rate": 0.30,
    "cross_domain_failure_rate": 0.20,
}


async def _get_layer1_config() -> dict:
    """从配置中心读取 Layer 1 规则引擎配置（禁止硬编码）"""
    return {
        "thresholds": {
            "p_at_5": await get_config_value(
                "rag_validation_threshold_p_at_5", _DEFAULT_THRESHOLDS["p_at_5"]
            ),
            "r_at_5": await get_config_value(
                "rag_validation_threshold_r_at_5", _DEFAULT_THRESHOLDS["r_at_5"]
            ),
            "f1": await get_config_value(
                "rag_validation_threshold_f1", _DEFAULT_THRESHOLDS["f1"]
            ),
            "mrr": await get_config_value(
                "rag_validation_threshold_mrr", _DEFAULT_THRESHOLDS["mrr"]
            ),
            "short_query_failure_rate": await get_config_value(
                "rag_validation_threshold_short_query_failure_rate",
                _DEFAULT_THRESHOLDS["short_query_failure_rate"],
            ),
            "cross_domain_failure_rate": await get_config_value(
                "rag_validation_threshold_cross_domain_failure_rate",
                _DEFAULT_THRESHOLDS["cross_domain_failure_rate"],
            ),
        },
        "param_safe_ranges": {},
    }


class Layer1RuleEngine:
    """Layer 1: 规则引擎"""

    def __init__(self, session_factory, test_run):
        self.session_factory = session_factory
        self.test_run = test_run
        self.thresholds = {}
        self.safe_ranges = _DEFAULT_PARAM_SAFE_RANGES

    async def execute(self) -> dict:
        """执行规则引擎"""
        config = await _get_layer1_config()
        self.thresholds = config["thresholds"]
        self.safe_ranges = config.get("param_safe_ranges") or _DEFAULT_PARAM_SAFE_RANGES

        async with self.session_factory() as session:
            metrics = await self._get_metrics(session)
            rag_config = await self._get_rag_config(session)

        suggestions = []

        # 规则 1-4: 指标阈值
        suggestions.extend(self._check_metric_rules(metrics, rag_config))

        # 规则 5: 短查询失败率
        if (
            metrics.get("short_query_failure_rate", 0)
            > self.thresholds["short_query_failure_rate"]
        ):
            if not rag_config.get("query_rewrite_enabled", False):
                suggestions.append(
                    {
                        "param": "query_rewrite_enabled",
                        "current": False,
                        "suggested": True,
                        "reason": f"短查询失败率超过 {self.thresholds['short_query_failure_rate']:.0%}，建议开启查询重写",
                        "priority": "function_switch",
                    }
                )

        # 规则 6: 跨领域失败率
        if (
            metrics.get("cross_domain_failure_rate", 0)
            > self.thresholds["cross_domain_failure_rate"]
        ):
            if not rag_config.get("synonym_expansion_enabled", False):
                suggestions.append(
                    {
                        "param": "synonym_expansion_enabled",
                        "current": False,
                        "suggested": True,
                        "reason": f"跨领域失败率超过 {self.thresholds['cross_domain_failure_rate']:.0%}，建议开启同义词扩展",
                        "priority": "function_switch",
                    }
                )

        # 规则 7: PageIndex 未启用
        if not rag_config.get("pageindex_enabled", False):
            suggestions.append(
                {
                    "param": "pageindex_enabled",
                    "current": False,
                    "suggested": True,
                    "reason": "PageIndex 未启用，建议开启以提升检索精度",
                    "priority": "function_switch",
                }
            )

        # 规则 8: 参数超出安全范围
        suggestions.extend(self._check_safe_ranges(rag_config))

        # 冲突检测与合并
        suggestions = self._detect_conflicts(suggestions)

        # 排序：安全范围修正 > 功能开关 > 参数调优
        priority_order = {"safe_range": 0, "function_switch": 1, "param_tuning": 2}
        suggestions.sort(key=lambda s: priority_order.get(s["priority"], 3))

        return {"suggestions": suggestions, "rules_triggered": len(suggestions)}

    def _check_metric_rules(self, metrics: dict, config: dict) -> list:
        """检查指标相关规则"""
        suggestions = []

        p_at_5 = metrics.get("p_at_5", 1.0)
        r_at_5 = metrics.get("r_at_5", 1.0)
        f1 = metrics.get("f1", 1.0)
        mrr = metrics.get("mrr", 1.0)

        # P@5 不达标
        if p_at_5 < self.thresholds["p_at_5"]:
            if r_at_5 >= 0.95:
                pass
            else:
                suggestions.append(
                    self._suggest_param_increase("bm25_top_k", config, "P@5 不达标")
                )
                suggestions.append(
                    self._suggest_param_increase("vector_top_k", config, "P@5 不达标")
                )

        # R@5 不达标
        if r_at_5 < self.thresholds["r_at_5"]:
            if p_at_5 >= 0.85:
                suggestions.append(
                    self._suggest_param_increase(
                        "vector_top_k", config, "R@5 不达标，优先增加 vector_top_k"
                    )
                )
            else:
                suggestions.append(
                    self._suggest_param_increase("bm25_top_k", config, "R@5 不达标")
                )

        # F1 不达标
        if f1 < self.thresholds["f1"]:
            current_ft = config.get("fusion_threshold", 0.25)
            delta = -0.05 if p_at_5 < r_at_5 else 0.05
            suggested = self._clamp_param("fusion_threshold", current_ft + delta)
            suggestions.append(
                {
                    "param": "fusion_threshold",
                    "current": current_ft,
                    "suggested": suggested,
                    "reason": f"F1 不达标 ({f1:.2f} < {self.thresholds['f1']})",
                    "priority": "param_tuning",
                }
            )

        # MRR 不达标
        if mrr < self.thresholds["mrr"]:
            suggestions.append(
                self._suggest_param_increase("reranker_initial_k", config, "MRR 不达标")
            )

        return suggestions

    def _suggest_param_increase(self, param: str, config: dict, reason: str) -> dict:
        """建议增加参数值"""
        safe_range = self.safe_ranges.get(param, {})
        current = config.get(param, safe_range.get("recommended", [10])[0])
        step = self._calc_adaptive_step(param, current)
        suggested = self._clamp_param(param, current + step)
        return {
            "param": param,
            "current": current,
            "suggested": suggested,
            "reason": reason,
            "priority": "param_tuning",
        }

    def _calc_adaptive_step(self, param: str, current: float) -> float:
        """自适应步长 = max(1, min(5, int(当前值 × 0.3)))"""
        step = max(1, min(5, int(current * 0.3)))
        return step

    def _clamp_param(self, param: str, value: float) -> float:
        """限制参数在安全范围内"""
        safe_range = _DEFAULT_PARAM_SAFE_RANGES.get(param, {})
        if not safe_range:
            return value
        return max(safe_range["min"], min(safe_range["max"], value))

    def _check_safe_ranges(self, config: dict) -> list:
        """检查参数是否超出安全范围"""
        suggestions = []
        for param, safe_range in self.safe_ranges.items():
            current = config.get(param)
            if current is not None:
                if current < safe_range["min"] or current > safe_range["max"]:
                    corrected = self._clamp_param(param, current)
                    suggestions.append(
                        {
                            "param": param,
                            "current": current,
                            "suggested": corrected,
                            "reason": f"参数超出安全范围 [{safe_range['min']}, {safe_range['max']}]",
                            "priority": "safe_range",
                        }
                    )
        return suggestions

    async def _get_metrics(self, session) -> dict:
        """从 TestRun 聚合获取指标数据"""
        from sqlalchemy import select

        from src.models.rag_eval.test_run import RagEvalTestRun

        result = await session.execute(
            select(RagEvalTestRun).where(RagEvalTestRun.id == self.test_run.id)
        )
        run = result.scalar_one_or_none()

        if not run:
            return {}

        metrics = {
            "p_at_5": run.overall_precision or 1.0,
            "r_at_5": run.overall_recall or 1.0,
            "f1": run.overall_f1 or 1.0,
            "mrr": run.overall_mrr or 1.0,
            "ndcg": run.overall_ndcg or 1.0,
            "short_query_failure_rate": 0.0,
            "cross_domain_failure_rate": 0.0,
        }

        return metrics

    async def _get_rag_config(self, session) -> dict:
        """从 ConfigVersion 获取当前配置快照"""
        from sqlalchemy import select

        from src.models.rag_eval.config_version import RagEvalConfigVersion

        if not self.test_run.config_version_id:
            return {}

        result = await session.execute(
            select(RagEvalConfigVersion).where(
                RagEvalConfigVersion.id == self.test_run.config_version_id
            )
        )
        config_version = result.scalar_one_or_none()

        if not config_version:
            return {}

        return config_version.config_snapshot or {}

    def _detect_conflicts(self, suggestions: list) -> list:
        """冲突检测与合并"""
        param_suggestions = {}
        for s in suggestions:
            param = s["param"]
            if param in param_suggestions:
                existing = param_suggestions[param]
                current = existing.get("current", 0)
                existing_dir = existing["suggested"] - current
                new_dir = s["suggested"] - current
                if existing_dir * new_dir < 0:
                    existing["conflict"] = True
                    existing["conflict_warning"] = (
                        f"参数冲突: {existing['reason']} 建议 {existing['suggested']}，"
                        f"{s['reason']} 建议 {s['suggested']}，交由用户决策"
                    )
                else:
                    existing["suggested"] = max(existing["suggested"], s["suggested"])
            else:
                param_suggestions[param] = s
        return list(param_suggestions.values())
