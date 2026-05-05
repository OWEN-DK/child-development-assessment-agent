"""报告引擎门面——生成、查询、趋势分析与导出"""

from src.repository.rag_eval.report_repository import ReportRepository
from src.repository.rag_eval.test_run_repository import TestRunRepository
from src.schemas.rag_eval.report import (
    BadCaseEntry, DiagnosisSection, EvalReportList, EvalReportRead,
    OverallSummary, ScoringDashboard, TrendData, TuningEntry,
)
from src.service.rag_eval.report.builder import ReportBuilder
from src.service.rag_eval.report.exporter import ReportExporter
from src.service.rag_eval.report.markdown_renderer import MarkdownRenderer
from src.service.rag_eval.report.trend_analyzer import TrendAnalyzer
from src.utils.exceptions import AppException, ReportNotFoundException, TestRunNotFoundException
from src.utils.id_generator import generate_id
from src.utils.orm_mapper import OrmMapper


class ReportEngineFacade:
    """报告引擎门面——协调 ReportBuilder/MarkdownRenderer/TrendAnalyzer/ReportExporter"""

    def __init__(self, builder, markdown_renderer, trend_analyzer, exporter,
                 report_repository, test_run_repository, orm_mapper=None,
                 metric_engine=None, run_engine=None):
        self._b = builder; self._r = markdown_renderer; self._t = trend_analyzer
        self._e = exporter; self._rr = report_repository; self._tr = test_run_repository
        self._m = orm_mapper or OrmMapper()
        self._metric = metric_engine
        self._run = run_engine

    async def generate_report(self, run_id: str) -> EvalReportRead:
        """生成完整评估报告：build→render→save→return

        如果指标尚未计算，自动触发双轨评估补算。
        """
        run = await self._tr.get_by_id(run_id)
        if run is None:
            raise TestRunNotFoundException(run_id)
        if run.status != "completed":
            raise AppException(400, 13001, f"运行状态为 {run.status} 非 completed", "TEST_RUN_NOT_COMPLETED")

        # 指标缺失时自动补算
        if not run.l1_metrics_json:
            if not self._metric or not self._run:
                raise AppException(400, 13023, "运行尚未完成指标计算，无法生成报告", "METRICS_NOT_COMPUTED")
            await self._compute_metrics(run_id, run)

        data = await self._b.build(run_id)
        md = self._r.render(data)

        await self._supersede(run_id)

        rid = generate_id()
        orm = await self._rr.create({
            "id": rid, "run_id": run_id,
            "test_set_id": run.test_set_ids[0] if run.test_set_ids else None,
            "config_version_id": getattr(run, "config_version_id", None),
            "overall_score": data.summary.overall_score,
            "l1_score": data.summary.l1_score,
            "l2_score": data.summary.l2_score,
            "l3_score": data.summary.l3_score,
            "metrics_json": data.model_dump(mode="json"),
            "diagnosis_json": {"sections": [s.model_dump(mode="json") for s in data.diagnosis_details],
                               "overall_health": data.summary.diagnosis_health},
            "bad_cases_json": [c.model_dump(mode="json") for c in data.bad_cases],
            "suggestions_json": [s.model_dump(mode="json") for s in data.tuning_suggestions],
            "markdown_content": md, "status": "completed",
        })
        return self._to_read(orm)

    async def get_report(self, report_id: str) -> EvalReportRead:
        r = await self._rr.get_by_id(report_id)
        if r is None:
            raise ReportNotFoundException(report_id)
        return self._to_read(r)

    async def list_reports(self, page=1, page_size=20, test_set_id=None) -> EvalReportList:
        if test_set_id:
            reports = await self._rr.get_by_test_set_id(test_set_id, skip=(page - 1) * page_size, limit=page_size)
            total = await self._rr.count_by_filter(test_set_id=test_set_id)
        else:
            reports = await self._rr.get_by_status("completed", skip=(page - 1) * page_size, limit=page_size)
            total = await self._rr.count_by_filter(status="completed")
        return EvalReportList(
            items=[self._to_read(r) for r in reports],
            total=total, page=page, page_size=page_size,
        )

    async def get_trend(self, metric=None, limit=10) -> TrendData:
        return await self._t.get_trend(metric=metric, limit=limit)

    async def export_report(self, report_id: str, format="markdown") -> bytes:
        report = await self.get_report(report_id)
        if format == "json":
            return await self._e.export_json(report)
        elif format == "csv":
            return await self._e.export_csv(report)
        elif format == "pdf":
            return await self._e.export_pdf(report)
        return await self._e.export_markdown(report)

    def _to_read(self, orm) -> EvalReportRead:
        """将 ORM 模型转换为 EvalReportRead（从 metrics_json 重建结构化字段）"""
        metrics_json = orm.metrics_json or {}

        # 从 metrics_json（EvalReportData 的 dump）重建结构化对象
        summary = OverallSummary.model_validate(metrics_json.get("summary", {}))
        dashboard = ScoringDashboard.model_validate(metrics_json.get("scoring_dashboard", {}))
        diagnosis = [DiagnosisSection.model_validate(s) for s in metrics_json.get("diagnosis_details", [])]
        bad_cases = [BadCaseEntry.model_validate(c) for c in metrics_json.get("bad_cases", [])]
        tuning = [TuningEntry.model_validate(t) for t in metrics_json.get("tuning_suggestions", [])]

        return EvalReportRead(
            id=orm.id,
            run_id=orm.run_id,
            test_set_id=orm.test_set_id,
            config_version_id=orm.config_version_id,
            status=orm.status,
            summary=summary,
            scoring_dashboard=dashboard,
            diagnosis_details=diagnosis,
            bad_cases=bad_cases,
            tuning_suggestions=tuning,
            markdown_content=orm.markdown_content,
            created_at=orm.created_at,
        )

    async def delete_report(self, report_id: str) -> None:
        """删除单个报告"""
        r = await self._rr.get_by_id(report_id)
        if r is None:
            raise ReportNotFoundException(report_id)
        await self._rr.delete(report_id)

    async def batch_delete_reports(self, report_ids: list[str]) -> None:
        """批量删除报告"""
        for rid in report_ids:
            try:
                await self._rr.delete(rid)
            except Exception:
                pass

    async def _compute_metrics(self, run_id: str, run) -> None:
        """自动补算指标：获取结果→计算→保存"""
        from src.utils.logger import logger
        try:
            results = await self._run.get_run_results(run_id)
            if not results:
                raise AppException(400, 13023, "运行结果为空，无法计算指标", "METRICS_NOT_COMPUTED")
            metrics, diagnosis = await self._metric.calculate_and_diagnose(
                run_id, results, run_data=run,
            )
            l1_details = metrics.l1.context_precision.details or {}
            if not l1_details.get("case_count"):
                raise AppException(400, 13023, "指标计算结果为空", "METRICS_NOT_COMPUTED")
            await self._run.save_evaluation(run_id, metrics, diagnosis)
            logger.info(f"运行[{run_id}] 指标自动补算完成")
        except AppException:
            raise
        except Exception as e:
            logger.error(f"运行[{run_id}] 指标自动补算失败: {e}", exc_info=True)
            raise AppException(400, 13023, f"指标计算失败: {e}", "METRICS_NOT_COMPUTED")

    async def _supersede(self, run_id: str):
        """将同 run 的旧 completed 报告标记为 superseded"""
        for r in await self._rr.get_by_run_id(run_id):
            if r.status == "completed":
                await self._rr.update(r.id, {"status": "superseded"})

    async def cleanup_expired_reports(self, retention_days: int = 30) -> int:
        """清理过期的报告"""
        from datetime import datetime, timedelta
        from sqlalchemy import select
        from src.models.rag_eval.report import EvalReport
        
        cutoff = datetime.now() - timedelta(days=retention_days)
        
        async with self._rr.db_session_factory() as session:
            stmt = select(EvalReport).where(
                EvalReport.created_at < cutoff,
            )
            result = await session.execute(stmt)
            old_reports = result.scalars().all()
            
        cleaned_count = 0
        for report in old_reports:
            try:
                await self._rr.delete(report.id)
                cleaned_count += 1
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(f"清理报告 {report.id} 失败: {e}")
                
        return cleaned_count
