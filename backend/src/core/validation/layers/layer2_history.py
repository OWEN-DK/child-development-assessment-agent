import logging
from typing import Any

from sqlalchemy import select
from src.models.rag_eval.test_run import RagEvalTestRun
from src.models.rag_eval.tuning_suggestion import RagEvalTuningSuggestionRecord

logger = logging.getLogger(__name__)


class Layer2HistoryComparison:
    """Layer 2: 历史对比"""

    def __init__(self, session_factory, test_run):
        self.session_factory = session_factory
        self.test_run = test_run

    async def execute(self) -> dict:
        """执行历史对比"""
        async with self.session_factory() as session:
            history_runs = await self._get_history_runs(session)

            if not history_runs:
                return {
                    "status": "baseline",
                    "data": {
                        "message": "运行更多次后可获得历史对比分析",
                        "current_metrics": {
                            "p_at_5": self.test_run.overall_precision,
                            "r_at_5": self.test_run.overall_recall,
                            "f1": self.test_run.overall_f1,
                            "mrr": self.test_run.overall_mrr,
                        },
                    },
                }

            history_refs = []

            # 规则 1: 配置变更→指标变化关联
            config_changes = await self._extract_config_changes(history_runs, session)
            history_refs.append(
                {
                    "type": "config_change_correlation",
                    "changes": config_changes,
                }
            )

            # 规则 2: 相似问题匹配
            bad_cases = await self._get_bad_cases(session)
            similar_matches = await self._match_similar_issues(
                bad_cases, history_runs, session
            )
            history_refs.append(
                {
                    "type": "similar_issue_matching",
                    "matches": similar_matches,
                }
            )

            return {
                "history_references": history_refs,
                "total_history_runs": len(history_runs),
            }

    async def _get_history_runs(self, session) -> list[RagEvalTestRun]:
        """获取同一 test_set_id 的历史运行"""
        stmt = (
            select(RagEvalTestRun)
            .where(RagEvalTestRun.test_set_id == self.test_run.test_set_id)
            .where(RagEvalTestRun.id != self.test_run.id)
            .where(RagEvalTestRun.status == "completed")
            .order_by(RagEvalTestRun.created_at.desc())
            .limit(10)
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def _extract_config_changes(
        self, history_runs: list[RagEvalTestRun], session
    ) -> list:
        """提取配置变更与指标变化"""
        from src.models.rag_eval.config_version import RagEvalConfigVersion

        changes = []
        current_config = await self._get_config_snapshot(
            session, self.test_run.config_version_id
        )

        for prev_run in history_runs:
            prev_config = await self._get_config_snapshot(
                session, prev_run.config_version_id
            )
            diff = self._json_diff(prev_config, current_config)

            if diff:
                metric_delta = self._calc_metric_delta(prev_run, self.test_run)
                changes.append(
                    {
                        "previous_run_id": prev_run.id,
                        "config_changes": diff,
                        "metric_changes": metric_delta,
                        "created_at": (
                            prev_run.created_at.isoformat()
                            if prev_run.created_at
                            else None
                        ),
                    }
                )

        return changes

    async def _get_config_snapshot(
        self, session, config_version_id: str | None
    ) -> dict:
        """获取配置快照"""
        if not config_version_id:
            return {}

        from src.models.rag_eval.config_version import RagEvalConfigVersion

        result = await session.execute(
            select(RagEvalConfigVersion).where(
                RagEvalConfigVersion.id == config_version_id
            )
        )
        config_version = result.scalar_one_or_none()

        if not config_version:
            return {}

        return config_version.config_snapshot or {}

    def _json_diff(self, old: dict, new: dict, prefix: str = "") -> list:
        """深度对比 JSON 对象，仅输出值发生变化的键值对"""
        changes = []
        all_keys = set(old.keys()) | set(new.keys())
        for key in all_keys:
            full_key = f"{prefix}.{key}" if prefix else key
            old_val = old.get(key)
            new_val = new.get(key)
            if isinstance(old_val, dict) and isinstance(new_val, dict):
                changes.extend(self._json_diff(old_val, new_val, prefix=full_key))
            elif old_val != new_val:
                changes.append(
                    {
                        "key": full_key,
                        "old_value": old_val,
                        "new_value": new_val,
                    }
                )
        return changes

    def _calc_metric_delta(
        self, old_run: RagEvalTestRun, new_run: RagEvalTestRun
    ) -> dict:
        """计算指标变化"""
        deltas = {}
        old_metrics = {
            "p_at_5": old_run.overall_precision or 0,
            "r_at_5": old_run.overall_recall or 0,
            "f1": old_run.overall_f1 or 0,
            "mrr": old_run.overall_mrr or 0,
        }
        new_metrics = {
            "p_at_5": new_run.overall_precision or 0,
            "r_at_5": new_run.overall_recall or 0,
            "f1": new_run.overall_f1 or 0,
            "mrr": new_run.overall_mrr or 0,
        }
        for key in new_metrics:
            if key in old_metrics:
                deltas[key] = new_metrics[key] - old_metrics[key]
        return deltas

    async def _get_bad_cases(self, session) -> list:
        """获取当前运行的 Bad Case 列表"""
        from src.models.rag_eval.test_run_result import RagEvalTestRunResult
        from src.models.rag_eval.test_case import RagEvalTestCase

        # 获取当前运行中失败的测试用例结果
        stmt = (
            select(RagEvalTestRunResult)
            .where(RagEvalTestRunResult.run_id == self.test_run.id)
            .where(RagEvalTestRunResult.hit_at_5 == False)
        )
        result = await session.execute(stmt)
        run_results = result.scalars().all()

        # 从测试用例中获取 domain 信息
        bad_cases = []
        for r in run_results:
            case_stmt = select(RagEvalTestCase).where(RagEvalTestCase.id == r.case_id)
            case_result = await session.execute(case_stmt)
            case = case_result.scalar_one_or_none()
            if case:
                bad_cases.append(
                    {
                        "case_id": r.case_id,
                        "query": r.query,
                        "domain": case.domain.value if case.domain else None,
                    }
                )

        return bad_cases

    async def _match_similar_issues(
        self, bad_cases: list, history_runs: list[RagEvalTestRun], session
    ) -> list:
        """基于失败模式标签匹配相似问题"""
        from src.models.rag_eval.test_report import RagEvalTestReport

        matches = []
        domains = list(set(bc.get("domain") for bc in bad_cases if bc.get("domain")))

        for domain in domains:
            # 获取当前测试集关联的报告 ID
            stmt_reports = select(RagEvalTestReport).where(
                RagEvalTestReport.test_run_id.in_(
                    [run.id for run in history_runs] + [self.test_run.id]
                )
            )
            result_reports = await session.execute(stmt_reports)
            reports = result_reports.scalars().all()
            report_ids = [r.id for r in reports]

            if report_ids:
                stmt = (
                    select(RagEvalTuningSuggestionRecord)
                    .where(
                        RagEvalTuningSuggestionRecord.source.in_(
                            ["rule_engine", "history", "llm"]
                        )
                    )
                    .where(RagEvalTuningSuggestionRecord.report_id.in_(report_ids))
                    .limit(5)
                )
                result = await session.execute(stmt)
                records = result.scalars().all()

                if records:
                    matches.append(
                        {
                            "domain": domain,
                            "resolved_count": len(records),
                            "suggestions": [
                                {
                                    "id": r.id,
                                    "suggestion": r.suggestion
                                    if hasattr(r, "suggestion")
                                    else r.reason,
                                    "source": (
                                        r.source.value if r.source else r.source
                                    ),
                                }
                                for r in records[:3]
                            ],
                        }
                    )

        return matches
