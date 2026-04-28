"""指标趋势分析器——按时间序列追踪指标变化"""

from datetime import datetime

from sqlalchemy import desc, select as _select

from src.repository.rag_eval.report_repository import ReportRepository
from src.repository.rag_eval.test_run_repository import TestRunRepository
from src.repository.rag_eval.config_version_repository import ConfigVersionRepository
from src.schemas.rag_eval.report import TrendData
from src.utils.exceptions import TestRunNotFoundException

_CORE = [
    "context_precision", "context_recall", "noise_sensitivity", "mrr", "ndcg",
    "faithfulness", "answer_relevancy", "groundedness", "overall_score",
]


class TrendAnalyzer:
    """指标趋势分析——按时间序列追踪，全部从数据库查询"""

    def __init__(self, report_repository, test_run_repository, config_version_repository):
        self._rr = report_repository
        self._tr = test_run_repository
        self._cr = config_version_repository

    async def get_trend(self, metric=None, limit=10) -> TrendData:
        """获取趋势数据：最近 limit 个 completed run 的指标变化"""
        runs = await self._tr.get_by_status("completed", skip=0, limit=limit)

        run_ids, timestamps, scores, cv_ids = [], [], [], []
        trends: dict[str, list[float]] = {}

        for run in runs:
            run_ids.append(run.id)
            timestamps.append(run.created_at)
            scores.append(run.overall_score or 0.0)
            cv_ids.append(run.config_version_id)
            mj = run.metrics_json or {} if hasattr(run, "metrics_json") else {}
            self._extract(mj, trends)

        return TrendData(run_ids=run_ids, timestamps=timestamps, overall_scores=scores,
                         metric_trends=trends, config_version_ids=cv_ids)

    async def get_run_delta(self, run_id: str) -> dict[str, float]:
        """计算指定 run 与前一次 completed run 的指标变化"""
        run = await self._tr.get_by_id(run_id)
        if run is None:
            raise TestRunNotFoundException(run_id)

        async with self._tr.db_session_factory() as session:
            result = await session.execute(
                _select(run.__class__)
                .where(run.__class__.status == "completed")
                .where(run.__class__.created_at < run.created_at)
                .order_by(desc(run.__class__.created_at)).limit(1))
            prev = result.scalar_one_or_none()

        if prev is None:
            return {}

        cm = run.metrics_json or {} if hasattr(run, "metrics_json") else {}
        pm = prev.metrics_json or {} if hasattr(prev, "metrics_json") else {}
        return {m: self._get(cm, m) - self._get(pm, m) for m in _CORE}

    def _extract(self, mj: dict, trends: dict[str, list[float]]):
        """从单次运行指标 JSON 中提取各指标值"""
        for name in _CORE:
            val = self._get(mj, name)
            trends.setdefault(name, []).append(val)

    def _get(self, mj: dict, name: str) -> float:
        """从指标 JSON 提取指定指标值"""
        if name == "overall_score":
            return float((mj or {}).get("overall_score", 0.0)) if isinstance(mj, dict) else 0.0
        for lk in ("l1", "l2", "l3"):
            ld = (mj or {}).get(lk, {}) if isinstance(mj, dict) else {}
            if isinstance(ld, dict) and name in ld:
                d = ld[name]
                return float(d.get("value", 0.0)) if isinstance(d, dict) else 0.0
        return 0.0
