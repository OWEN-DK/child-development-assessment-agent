"""报告控制器"""

from typing import Optional

from fastapi import APIRouter, Body, Path, Query
from fastapi.responses import Response

from src.api.sse import sse_response
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
        router.add_api_route("/reports/generation/{task_id}/stream", self.stream_report_generation, methods=["GET"])
        router.add_api_route("/reports/batch", self.batch_delete_reports, methods=["DELETE"])
        router.add_api_route("/reports/{report_id}", self.get_report, methods=["GET"])
        router.add_api_route("/reports/{report_id}", self.delete_report, methods=["DELETE"])
        router.add_api_route("/reports/{report_id}/export", self.export_report, methods=["GET"])
        router.add_api_route("/trends", self.get_trends, methods=["GET"])

    async def list_reports(
        self,
        page: int = Query(1, ge=1),
        page_size: int = Query(20, ge=1, le=100),
        run_id: Optional[str] = Query(None),
    ):
        result = await self._engine.list_reports(page, page_size, run_id=run_id)
        return APIResponse.success(result.model_dump(mode="json"))

    async def generate_report(self, body: dict = Body(...)):
        """生成报告，已有报告时返回 existing 状态，force=true 强制重新生成"""
        run_id = body.get("run_id", "")
        if not run_id:
            raise AppException(400, 13001, "run_id 不能为空", "DRAFT_NOT_FOUND")
        force = body.get("force", False)
        from src.utils.logger import logger
        logger.info(f"[报告生成] 收到请求 body={body}, force={force}, run_id={run_id}")
        result = await self._engine.start_generate_report(run_id, force=force)
        logger.info(f"[报告生成] 返回结果 result={result}")
        return APIResponse.success({**result, "run_id": run_id})

    async def stream_report_generation(self, task_id: str = Path(...)):
        """SSE 流：报告生成进度"""
        return sse_response(f"report_generation:{task_id}")

    async def get_report(self, report_id: str = Path(...)):
        result = await self._engine.get_report(report_id)
        return APIResponse.success(result.model_dump(mode="json"))

    async def delete_report(self, report_id: str = Path(...)):
        await self._engine.delete_report(report_id)
        return APIResponse.success(None)

    async def batch_delete_reports(self, body: dict = Body(...)):
        ids = body.get("ids", [])
        if not ids:
            raise AppException(400, 13002, "ids 不能为空", "INVALID_PARAMS")
        await self._engine.batch_delete_reports(ids)
        return APIResponse.success(None)

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
