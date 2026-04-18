"""历史对比分析:从历史运行中提取参数变更效果"""

from typing import Any, Dict, List, Optional

from src.schemas import HistoryReference
from src.utils.logger import logger


class HistoryAnalyzer:
    """历史对比分析:参数变更效果追踪"""

    METRICS_OF_INTEREST = [
        "overall_precision",
        "overall_recall",
        "overall_f1",
        "overall_mrr",
        "overall_ndcg",
    ]

    WEAKNESS_THRESHOLDS = {
        "overall_recall": 0.7,
        "overall_precision": 0.75,
        "overall_mrr": 0.65,
        "overall_ndcg": 0.75,
    }

    def __init__(self, test_run_repo=None, config_mgr=None):
        """初始化历史分析器"""
        self.test_run_repo = test_run_repo
        self.config_mgr = config_mgr

    async def analyze(
        self,
        current_metrics: Dict[str, float],
        current_run_id: str,
    ) -> List[HistoryReference]:
        """分析历史运行,返回参考建议"""
        history_runs = await self.test_run_repo.get_completed_runs(
            exclude_run_id=current_run_id,
            limit=20,
            order_by="created_at DESC",
        )

        if len(history_runs) < 2:
            logger.info("历史运行不足 2 次,跳过历史对比分析")
            return []

        references = []
        for i in range(len(history_runs) - 1):
            current_run = history_runs[i]
            previous_run = history_runs[i + 1]

            ref = await self._build_reference(current_run, previous_run)
            if ref:
                references.append(ref)

        if history_runs:
            latest_ref = await self._build_reference(
                history_runs[0],
                None,
                current_metrics=current_metrics,
            )
            if latest_ref:
                references.insert(0, latest_ref)

        logger.info(f"历史对比分析完成: 找到 {len(references)} 条历史参考")
        return references

    async def _build_reference(
        self,
        run: Any,
        previous_run: Optional[Any],
        current_metrics: Optional[Dict[str, float]] = None,
    ) -> Optional[HistoryReference]:
        """构建单条历史参考"""
        new_snapshot = await self._get_config_snapshot(run.config_version_id)
        if not new_snapshot:
            return None

        if previous_run:
            old_snapshot = await self._get_config_snapshot(
                previous_run.config_version_id
            )
            if not old_snapshot:
                return None

            changed_params = self._diff_configs(old_snapshot, new_snapshot)
            if not changed_params:
                return None

            metric_changes = self._diff_metrics_between_runs(previous_run, run)
        else:
            if not current_metrics:
                return None
            changed_params = {}
            metric_changes = self._diff_metrics_against_current(run, current_metrics)

        conclusion = self._generate_conclusion(
            changed_params, metric_changes, has_config_change=(previous_run is not None)
        )

        return HistoryReference(
            run_id=run.id,
            date=run.created_at.strftime("%Y-%m-%d") if run.created_at else "未知",
            changed_params=changed_params,
            metric_changes=metric_changes,
            conclusion=conclusion,
        )

    def _diff_configs(
        self, old_snapshot: Dict, new_snapshot: Dict
    ) -> Dict[str, Dict[str, Any]]:
        """对比两个配置快照,提取变更参数"""
        changed = {}
        all_keys = set(list(old_snapshot.keys()) + list(new_snapshot.keys()))

        for key in all_keys:
            old_val = old_snapshot.get(key)
            new_val = new_snapshot.get(key)

            if old_val != new_val:
                changed[key] = {"from": old_val, "to": new_val}

        return changed

    def _diff_metrics_between_runs(
        self, old_run: Any, new_run: Any
    ) -> Dict[str, Dict[str, Any]]:
        """对比两次运行之间的指标变化"""
        changes = {}

        for metric in self.METRICS_OF_INTEREST:
            old_val = getattr(old_run, metric, None)
            new_val = getattr(new_run, metric, None)

            if old_val is not None and new_val is not None:
                delta = new_val - old_val
                changes[metric] = {
                    "from": round(old_val, 4),
                    "to": round(new_val, 4),
                    "delta": f"{delta:+.4f}",
                }

        return changes

    def _diff_metrics_against_current(
        self, run: Any, current_metrics: Dict[str, float]
    ) -> Dict[str, Dict[str, Any]]:
        """对比历史运行与当前运行的指标差异"""
        changes = {}

        for metric in self.METRICS_OF_INTEREST:
            old_val = getattr(run, metric, None)
            new_val = current_metrics.get(metric)

            if old_val is not None and new_val is not None:
                delta = new_val - old_val
                changes[metric] = {
                    "from": round(old_val, 4),
                    "to": round(new_val, 4),
                    "delta": f"{delta:+.4f}",
                }

        return changes

    async def _get_config_snapshot(self, version_id: str) -> Optional[Dict]:
        """获取配置版本快照"""
        if not version_id:
            return None
        full_config = await self.config_mgr.get_version_config(version_id)
        return full_config

    def _generate_conclusion(
        self,
        changed_params: Dict[str, Dict[str, Any]],
        metric_changes: Dict[str, Dict[str, Any]],
        has_config_change: bool = True,
    ) -> str:
        """生成结论总结"""
        if not has_config_change:
            parts = []
            for metric, delta in metric_changes.items():
                parts.append(
                    f"{metric}: {delta['from']} → {delta['to']} ({delta['delta']})"
                )
            return "；".join(parts) if parts else "指标数据无显著变化"

        parts = []
        for param, change in changed_params.items():
            param_short = param.split("_")[-1]
            for metric, delta in metric_changes.items():
                parts.append(
                    f"修改 {param_short} 从 {change['from']} 到 {change['to']} 后，"
                    f"{metric} 变化了 {delta['delta']}"
                )

        return "；".join(parts) if parts else "参数有变更,但指标变化不明显"

    def _find_similar_runs(
        self,
        current_metrics: Dict[str, float],
        history_runs: List[Any],
    ) -> List[Any]:
        """查找指标短板相似的历史运行"""
        current_weakness = self._compute_weakness_vector(current_metrics)

        similar_runs = []
        for run in history_runs:
            run_metrics = {
                "overall_recall": getattr(run, "overall_recall", 0),
                "overall_precision": getattr(run, "overall_precision", 0),
                "overall_mrr": getattr(run, "overall_mrr", 0),
                "overall_ndcg": getattr(run, "overall_ndcg", 0),
            }
            run_weakness = self._compute_weakness_vector(run_metrics)

            similarity = self._jaccard_similarity(current_weakness, run_weakness)

            if similarity >= 0.5:
                similar_runs.append(run)

        return similar_runs

    def _compute_weakness_vector(self, metrics: Dict[str, float]) -> set:
        """计算指标短板向量"""
        weaknesses = set()
        for metric, threshold in self.WEAKNESS_THRESHOLDS.items():
            value = metrics.get(metric, 1.0)
            if value < threshold:
                weaknesses.add(metric)
        return weaknesses

    def _jaccard_similarity(self, set_a: set, set_b: set) -> float:
        """计算 Jaccard 相似度"""
        if not set_a and not set_b:
            return 0.0
        intersection = len(set_a & set_b)
        union = len(set_a | set_b)
        return intersection / union if union > 0 else 0.0
