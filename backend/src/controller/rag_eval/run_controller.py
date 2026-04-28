"""测试运行控制器"""

from typing import Optional

from fastapi import APIRouter, Body, Path, Query

from src.api.sse import sse_response
from src.schemas.common import APIResponse
from src.schemas.rag_eval.test_run import TestRunCreate
from src.service.rag_eval.run.facade import RunEngineFacade
from src.utils.exceptions import AppException


class RunController:
    """测试运行管理端点"""

    def __init__(self, run_engine: RunEngineFacade):
        self._engine = run_engine

    def register(self, router: APIRouter) -> None:
        router.add_api_route("/runs", self.create_run, methods=["POST"])
        router.add_api_route("/runs", self.list_runs, methods=["GET"])
        router.add_api_route("/runs/{run_id}", self.get_run, methods=["GET"])
        router.add_api_route("/runs/{run_id}", self.delete_run, methods=["DELETE"])
        router.add_api_route("/runs/batch", self.batch_delete_runs, methods=["DELETE"])
        router.add_api_route("/runs/{run_id}/execute/{case_id}", self.execute_single, methods=["POST"])
        router.add_api_route("/runs/{run_id}/stream", self.stream_run, methods=["GET"])
        router.add_api_route("/runs/compare", self.compare_runs, methods=["GET"])

    async def create_run(self, body: TestRunCreate = Body(...)):
        result = await self._engine.create_run(body)
        task_id = await self._engine.start_run(result.id)
        return APIResponse.success({"run": result.model_dump(mode="json"), "task_id": task_id})

    async def list_runs(
        self,
        status: Optional[str] = Query(None),
        test_set_id: Optional[str] = Query(None),
        page: int = Query(1, ge=1),
        page_size: int = Query(20, ge=1, le=100),
    ):
        result = await self._engine.list_runs(status, test_set_id, page, page_size)
        return APIResponse.success(result.model_dump(mode="json"))

    async def get_run(self, run_id: str = Path(...)):
        result = await self._engine.get_run(run_id)
        return APIResponse.success(result.model_dump(mode="json"))

    async def delete_run(self, run_id: str = Path(...)):
        await self._engine.delete_run(run_id)
        return APIResponse.success(None)

    async def batch_delete_runs(self, body: dict = Body(...)):
        run_ids = body.get("run_ids", [])
        if not run_ids:
            raise AppException(400, 13016, "run_ids 不能为空", "INVALID_TEST_CASE_FORMAT")
        await self._engine.batch_delete_runs(run_ids)
        return APIResponse.success(None)

    async def execute_single(self, run_id: str = Path(...), case_id: str = Path(...)):
        result = await self._engine.execute_single(run_id, case_id)
        return APIResponse.success(result.model_dump(mode="json"))

    async def stream_run(self, run_id: str = Path(...)):
        """SSE 测试运行进度"""
        channel = f"test_run:{run_id}"
        return sse_response(channel)

    async def compare_runs(
        self,
        run_id_1: str = Query(...),
        run_id_2: str = Query(...),
    ):
        result = await self._engine.compare_runs(run_id_1, run_id_2)
        return APIResponse.success(result.model_dump(mode="json"))
