"""测试用例与测试集控制器"""

from typing import Optional

from fastapi import APIRouter, Body, Path, Query

from src.schemas.common import APIResponse
from src.schemas.rag_eval.test_case import TestCaseCreate, TestCaseImportData, TestCaseUpdate
from src.schemas.rag_eval.test_set import TestSetCreate, TestSetUpdate
from src.service.rag_eval.case.facade import CaseEngineFacade
from src.utils.exceptions import AppException


class CaseController:
    """测试用例与测试集管理端点"""

    def __init__(self, case_engine: CaseEngineFacade):
        self._engine = case_engine

    def register(self, router: APIRouter) -> None:
        # 测试用例
        router.add_api_route("/test-cases", self.list_cases, methods=["GET"])
        router.add_api_route("/test-cases", self.create_case, methods=["POST"])
        router.add_api_route("/test-cases/{case_id}", self.get_case, methods=["GET"])
        router.add_api_route("/test-cases/{case_id}", self.update_case, methods=["PUT"])
        router.add_api_route("/test-cases/{case_id}", self.delete_case, methods=["DELETE"])
        router.add_api_route("/test-cases/batch", self.batch_delete_cases, methods=["DELETE"])
        router.add_api_route("/test-cases/import", self.import_cases, methods=["POST"])
        # 测试集
        router.add_api_route("/test-sets", self.list_sets, methods=["GET"])
        router.add_api_route("/test-sets", self.create_set, methods=["POST"])
        router.add_api_route("/test-sets/{set_id}", self.get_set, methods=["GET"])
        router.add_api_route("/test-sets/{set_id}", self.update_set, methods=["PUT"])
        router.add_api_route("/test-sets/{set_id}", self.delete_set, methods=["DELETE"])
        router.add_api_route("/test-sets/{set_id}/cases", self.add_cases_to_set, methods=["POST"])
        router.add_api_route("/test-sets/{set_id}/cases", self.remove_cases_from_set, methods=["DELETE"])
        router.add_api_route("/test-sets/{set_id}/export", self.export_set, methods=["GET"])

    async def list_cases(
        self,
        page: int = Query(1, ge=1),
        page_size: int = Query(20, ge=1, le=100),
        domain: Optional[str] = Query(None),
    ):
        result = await self._engine.list_cases(page, page_size, domain)
        return APIResponse.success(result.model_dump(mode="json"))

    async def create_case(self, body: TestCaseCreate = Body(...)):
        result = await self._engine.create_case(body)
        return APIResponse.success(result.model_dump(mode="json"))

    async def get_case(self, case_id: str = Path(...)):
        result = await self._engine.get_case(case_id)
        return APIResponse.success(result.model_dump(mode="json"))

    async def update_case(self, case_id: str = Path(...), body: TestCaseUpdate = Body(...)):
        result = await self._engine.update_case(case_id, body)
        return APIResponse.success(result.model_dump(mode="json"))

    async def delete_case(self, case_id: str = Path(...)):
        await self._engine.delete_case(case_id)
        return APIResponse.success(None)

    async def batch_delete_cases(self, body: dict = Body(...)):
        case_ids = body.get("case_ids", [])
        if not case_ids:
            raise AppException(400, 13016, "case_ids 不能为空", "INVALID_TEST_CASE_FORMAT")
        await self._engine.batch_delete_cases(case_ids)
        return APIResponse.success(None)

    async def import_cases(self, body: TestCaseImportData = Body(...)):
        result = await self._engine.import_from_json(body)
        return APIResponse.success(result.model_dump(mode="json"))

    async def list_sets(self):
        result = await self._engine.list_sets()
        return APIResponse.success([r.model_dump(mode="json") for r in result])

    async def create_set(self, body: TestSetCreate = Body(...)):
        result = await self._engine.create_set(body)
        return APIResponse.success(result.model_dump(mode="json"))

    async def get_set(self, set_id: str = Path(...)):
        result = await self._engine.get_set(set_id)
        return APIResponse.success(result.model_dump(mode="json"))

    async def update_set(self, set_id: str = Path(...), body: TestSetUpdate = Body(...)):
        result = await self._engine.update_set(set_id, body)
        return APIResponse.success(result.model_dump(mode="json"))

    async def delete_set(self, set_id: str = Path(...)):
        await self._engine.delete_set(set_id)
        return APIResponse.success(None)

    async def add_cases_to_set(self, set_id: str = Path(...), body: dict = Body(...)):
        case_ids = body.get("case_ids", [])
        if not case_ids:
            raise AppException(400, 13016, "case_ids 不能为空", "INVALID_TEST_CASE_FORMAT")
        result = await self._engine.add_cases_to_set(set_id, case_ids)
        return APIResponse.success(result.model_dump(mode="json"))

    async def remove_cases_from_set(self, set_id: str = Path(...), body: dict = Body(...)):
        case_ids = body.get("case_ids", [])
        if not case_ids:
            raise AppException(400, 13016, "case_ids 不能为空", "INVALID_TEST_CASE_FORMAT")
        result = await self._engine.remove_cases_from_set(set_id, case_ids)
        return APIResponse.success(result.model_dump(mode="json"))

    async def export_set(self, set_id: str = Path(...)):
        result = await self._engine.export_set(set_id)
        return APIResponse.success(result.model_dump(mode="json"))
