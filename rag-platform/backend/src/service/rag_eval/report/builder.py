"""评估报告构建器

从测试运行结果和指标构建完整的评估报告。
包含跨域分析章节（域贡献度、冲突统计、延迟分布）。
"""
import json
import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy.ext.asyncio import async_sessionmaker

from src.models.rag_eval.test_run import TestRun
from src.repository.rag_eval.report_repo import ReportRepository
from src.repository.rag_eval.test_run_repo import TestRunResultRepository
from src.schemas.rag_eval.report import ReportRead
from src.service.rag_eval.report.markdown_renderer import MarkdownRenderer
from src.service.rag_eval.run.result_processor import ResultProcessor
from src.utils.logger import logger


class ReportBuilder:
    """评估报告构建器

    从运行结果和指标构建完整的 EvalReportData。
    自动 supersede 同一运行之前的报告。
    """

    def __init__(
        self,
        session_factory: async_sessionmaker,
        report_repo: ReportRepository,
        result_repo: TestRunResultRepository,
        result_processor: ResultProcessor,
    ):
        self._session_factory = session_factory
        self._report_repo = report_repo
        self._result_repo = result_repo
        self._result_processor = result_processor
        self._renderer = MarkdownRenderer()

    async def build(
        self,
        run: TestRun,
        l1_metrics: Optional[dict[str, Any]] = None,
        l2_metrics: Optional[dict[str, Any]] = None,
        l3_metrics: Optional[dict[str, Any]] = None,
        cross_domain_metrics: Optional[dict[str, Any]] = None,
        diagnosis_json: Optional[dict[str, Any]] = None,
        tuning_suggestions: Optional[list[dict[str, Any]]] = None,
    ) -> ReportRead:
        """构建评估报告

        步骤：
        1. 收集所有执行结果和指标数据
        2. 构建跨域分析章节
        3. 构建失败用例收集
        4. 生成 Markdown 内容
        5. supersede 旧报告
        6. 写 MySQL
        """
        # 1. 收集结果
        results = await self._result_repo.list_results(run.id)

        # 2. 聚合结果
        summary = await self._result_processor.process(run)

        # 3. 构建跨域分析章节
        cross_domain_section = self._build_cross_domain_section(
            results=results,
            cross_domain_metrics=cross_domain_metrics,
        )

        # 4. 收集失败用例
        bad_cases = self._collect_bad_cases(results)

        # 5. 计算总体得分
        l1_score = l1_metrics.get("avg_score", 0) if l1_metrics else 0
        l2_score = l2_metrics.get("avg_score", 0) if l2_metrics else 0
        l3_score = l3_metrics.get("avg_score", 0) if l3_metrics else 0
        cross_domain_score = (
            self._compute_cross_domain_score(cross_domain_metrics)
            if cross_domain_metrics
            else None
        )

        overall_score = self._compute_overall_score(
            l1_score=l1_score,
            l2_score=l2_score,
            l3_score=l3_score,
            cross_domain_score=cross_domain_score,
        )

        # 6. 生成 Markdown
        markdown = self._renderer.render_full_report(
            run_id=run.id,
            run_name=run.name or "",
            pipeline_id=run.pipeline_id,
            pipeline_version=run.pipeline_version,
            overall_score=overall_score,
            l1_metrics=l1_metrics,
            l2_metrics=l2_metrics,
            l3_metrics=l3_metrics,
            cross_domain_section=cross_domain_section,
            bad_cases=bad_cases,
            tuning_suggestions=tuning_suggestions,
            diagnosis_json=diagnosis_json,
        )

        # 7. 构建报告数据
        report_id = f"rpt_{int(datetime.utcnow().timestamp())}_{uuid.uuid4().hex[:8]}"
        metrics_json = {
            "l1": l1_metrics,
            "l2": l2_metrics,
            "l3": l3_metrics,
        }

        report_data = {
            "id": report_id,
            "run_id": run.id,
            "tenant_id": run.tenant_id,
            "overall_score": overall_score,
            "l1_score": l1_score,
            "l2_score": l2_score,
            "l3_score": l3_score,
            "cross_domain_score": cross_domain_score,
            "metrics_json": metrics_json,
            "diagnosis_json": diagnosis_json,
            "bad_cases_json": bad_cases,
            "suggestions_json": {"items": tuning_suggestions or []},
            "cross_domain_json": cross_domain_section,
            "markdown_content": markdown,
            "status": "completed",
        }

        # 8. supersede 旧报告
        await self._supersede_old_reports(run.id, run.tenant_id)

        # 9. 创建新报告
        report = await self._report_repo.create(report_data)
        logger.info(f"报告生成完成: {report_id}, run={run.id}, score={overall_score:.4f}")

        return ReportRead.model_validate(report)

    def _build_cross_domain_section(
        self,
        results: list[Any],
        cross_domain_metrics: Optional[dict[str, Any]],
    ) -> Optional[dict[str, Any]]:
        """构建跨域分析章节"""
        if not cross_domain_metrics:
            return None

        # 从结果聚合域贡献度
        domain_contributions = []
        domain_stats: dict[str, dict[str, Any]] = {}

        for r in results:
            domain_json = r.domain_results_json or {}
            for domain_id, info in domain_json.items():
                if domain_id not in domain_stats:
                    domain_stats[domain_id] = {
                        "hit_count": 0,
                        "total_contribution": 0.0,
                        "query_count": 0,
                    }
                ds = domain_stats[domain_id]
                ds["hit_count"] += info.get("hit_count", 0)
                ds["total_contribution"] += info.get("contribution", 0.0)
                ds["query_count"] += 1

        total_queries = len(results)
        for domain_id, ds in domain_stats.items():
            domain_contributions.append({
                "domain_id": domain_id,
                "domain_name": domain_id,  # 后续可从知识库名称映射
                "contribution_score": round(
                    ds["total_contribution"] / ds["query_count"], 4
                ) if ds["query_count"] > 0 else 0.0,
                "activation_accuracy": round(
                    ds["query_count"] / total_queries, 4
                ) if total_queries > 0 else 0.0,
                "chunk_count": ds["hit_count"],
            })

        # 延迟分布
        latency = cross_domain_metrics.get("latency", {})

        return {
            "domain_contributions": domain_contributions,
            "overall_activation_accuracy": cross_domain_metrics.get("activation_accuracy", 0),
            "overall_cross_coverage": cross_domain_metrics.get("cross_coverage", 0),
            "overall_conflict_detection_rate": cross_domain_metrics.get("conflict_detection_rate", 0),
            "e2e_latency_distribution": {
                "p50_ms": latency.get("p50_ms", 0),
                "p95_ms": latency.get("p95_ms", 0),
                "p99_ms": latency.get("p99_ms", 0),
                "avg_ms": latency.get("avg_ms", 0),
            },
            "domain_conflicts": cross_domain_metrics.get("conflicts", []),
        }

    def _collect_bad_cases(self, results: list[Any]) -> dict[str, Any]:
        """收集失败用例（未通过或出错的用例）"""
        bad = []
        for r in results:
            if r.passed == 0 or r.error_message:
                bad.append({
                    "case_id": r.test_case_id,
                    "query": r.query,
                    "passed": r.passed,
                    "error": r.error_message,
                    "precision": float(r.precision) if r.precision else None,
                    "recall": float(r.recall) if r.recall else None,
                    "f1": float(r.f1) if r.f1 else None,
                    "elapsed_ms": r.execution_time_ms,
                })
        return {"total": len(bad), "items": bad}

    def _compute_cross_domain_score(
        self, cross_domain_metrics: dict[str, Any]
    ) -> Optional[float]:
        """计算跨域综合得分"""
        valid_scores = []
        for key in ["domain_activation_accuracy", "cross_domain_coverage",
                     "conflict_detection_rate"]:
            val = cross_domain_metrics.get(key)
            if val is not None and val >= 0:
                valid_scores.append(float(val))
        return round(sum(valid_scores) / len(valid_scores), 4) if valid_scores else None

    def _compute_overall_score(
        self,
        l1_score: float,
        l2_score: float,
        l3_score: float,
        cross_domain_score: Optional[float],
    ) -> float:
        """加权综合得分"""
        weights = {"l1": 0.4, "l2": 0.4, "l3": 0.15, "cross_domain": 0.05}
        total_w = weights["l1"] + weights["l2"] + weights["l3"]
        weighted_sum = (
            l1_score * weights["l1"]
            + l2_score * weights["l2"]
            + l3_score * weights["l3"]
        )
        if cross_domain_score is not None and cross_domain_score >= 0:
            total_w += weights["cross_domain"]
            weighted_sum += cross_domain_score * weights["cross_domain"]
        return round(weighted_sum / total_w, 4) if total_w > 0 else 0.0

    async def _supersede_old_reports(self, run_id: str, tenant_id: str):
        """将同运行的旧报告标记为 superseded"""
        from sqlalchemy import select, update
        from src.models.rag_eval.eval_report import EvalReport

        async with self._session_factory() as session:
            stmt = (
                update(EvalReport)
                .where(
                    EvalReport.run_id == run_id,
                    EvalReport.status == "completed",
                )
                .values(status="superseded")
            )
            await session.execute(stmt)
            await session.commit()
