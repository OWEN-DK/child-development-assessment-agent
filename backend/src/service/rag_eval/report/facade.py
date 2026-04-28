"""报告引擎门面——生成、查询、趋势分析与导出"""

from src.repository.rag_eval.report_repository import ReportRepository
from src.repository.rag_eval.test_run_repository import TestRunRepository
from src.schemas.rag_eval.report import EvalReportRead, TrendData
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
                 report_repository, test_run_repository, orm_mapper=None):
        self._b = builder; self._r = markdown_renderer; self._t = trend_analyzer
        self._e = exporter; self._rr = report_repository; self._tr = test_run_repository
        self._m = orm_mapper or OrmMapper()

    async def generate_report(self, run_id: str) -> EvalReportRead:
        """生成完整评估报告：build→render→save→return"""
        run = await self._tr.get_by_id(run_id)
        if run is None:
            raise TestRunNotFoundException(run_id)
        if run.status != "completed":
            raise AppException(400, 13001, f"运行状态为 {run.status} 非 completed", "TEST_RUN_NOT_COMPLETED")

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
        return self._m.to_read(orm, EvalReportRead)

    async def get_report(self, report_id: str) -> EvalReportRead:
        r = await self._rr.get_by_id(report_id)
        if r is None:
            raise ReportNotFoundException(report_id)
        return self._m.to_read(r, EvalReportRead)

    async def list_reports(self, page=1, page_size=20, test_set_id=None) -> list[EvalReportRead]:
        if test_set_id:
            reports = await self._rr.get_by_test_set_id(test_set_id, skip=(page - 1) * page_size, limit=page_size)
        else:
            reports = await self._rr.get_by_status("completed", skip=(page - 1) * page_size, limit=page_size)
        return [self._m.to_read(r, EvalReportRead) for r in reports]

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
