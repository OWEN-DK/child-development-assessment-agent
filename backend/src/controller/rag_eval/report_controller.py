"""报告控制器"""

from typing import Optional

from fastapi import APIRouter, Body, Path, Query
from fastapi.responses import Response

from src.schemas.common import APIResponse
from src.service.rag_eval.report.facade import ReportEngineFacade
from src.utils.exceptions import AppException


class ReportController:
    """报告管理端点"""

    def __init__(self, report_engine: ReportEngineFacade):
        self._engine = report_engine

    def register(self, router: APIRouter) -> None:
        router.add_api_route("/reports", self.list_reports, methods=["GET"])
        router.add_api_route("/reports", self.generate_report, methods=["POST"])
        router.add_api_route("/reports/{report_id}", self.get_report, methods=["GET"])
        router.add_api_route("/reports/{report_id}/export", self.export_report, methods=["GET"])
        router.add_api_route("/trends", self.get_trends, methods=["GET"])

    async def list_reports(
        self,
        page: int = Query(1, ge=1),
        page_size: int = Query(20, ge=1, le=100),
    ):
        result = await self._engine.list_reports(page, page_size)
        return APIResponse.success([r.model_dump(mode="json") for r in result])

    async def generate_report(self, body: dict = Body(...)):
        run_id = body.get("run_id", "")
        if not run_id:
            raise AppException(400, 13001, "run_id 不能为空", "DRAFT_NOT_FOUND")
        result = await self._engine.generate_report(run_id)
        return APIResponse.success(result.model_dump(mode="json"))

    async def get_report(self, report_id: str = Path(...)):
        result = await self._engine.get_report(report_id)
        return APIResponse.success(result.model_dump(mode="json"))

    async def export_report(
        self,
        report_id: str = Path(...),
        format: str = Query("markdown"),
    ):
        result_bytes = await self._engine.export_report(report_id, format)
        media_map = {
            "json": "application/json",
            "csv": "text/csv",
            "pdf": "application/pdf",
            "markdown": "text/markdown",
        }
        return Response(
            content=result_bytes,
            media_type=media_map.get(format, "text/plain"),
        )

    async def get_trends(
        self,
        metric: Optional[str] = Query(None),
        limit: int = Query(10, ge=1, le=50),
    ):
        result = await self._engine.get_trend(metric, limit)
        return APIResponse.success(result.model_dump(mode="json"))
