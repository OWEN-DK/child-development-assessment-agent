"""用例/测试集引擎门面"""

from src.schemas.rag_eval.test_case import (
    TestCaseCreate,
    TestCaseImportData,
    TestCaseList,
    TestCaseRead,
    TestCaseUpdate,
)
from src.schemas.rag_eval.test_set import (
    TestSetCreate,
    TestSetExport,
    TestSetRead,
    TestSetUpdate,
)
from src.service.rag_eval.case.case_service import CaseService
from src.service.rag_eval.case.set_service import SetService


class CaseEngineFacade:
    """用例/测试集引擎门面"""

    def __init__(
        self,
        case_service: CaseService,
        set_service: SetService,
    ):
        self._case = case_service
        self._set = set_service

    # ── 测试用例 ──

    async def create_case(self, data: TestCaseCreate) -> TestCaseRead:
        return await self._case.create(data)

    async def get_case(self, case_id: str) -> TestCaseRead:
        return await self._case.get(case_id)

    async def update_case(self, case_id: str, data: TestCaseUpdate) -> TestCaseRead:
        return await self._case.update(case_id, data)

    async def delete_case(self, case_id: str) -> None:
        await self._case.delete(case_id)

    async def list_cases(
        self,
        page: int = 1,
        page_size: int = 20,
        domain: str | None = None,
        age_stage_label: str | None = None,
        source: str | None = None,
    ) -> TestCaseList:
        return await self._case.list_cases(page, page_size, domain, age_stage_label, source)

    async def batch_delete_cases(self, case_ids: list[str]) -> None:
        await self._case.batch_delete(case_ids)

    async def import_from_json(self, data: TestCaseImportData) -> TestCaseList:
        return await self._case.import_from_json(data)

    # ── 测试集 ──

    async def create_set(self, data: TestSetCreate) -> TestSetRead:
        return await self._set.create(data)

    async def get_set(self, set_id: str) -> TestSetRead:
        return await self._set.get(set_id)

    async def update_set(self, set_id: str, data: TestSetUpdate) -> TestSetRead:
        return await self._set.update(set_id, data)

    async def delete_set(self, set_id: str) -> None:
        await self._set.delete(set_id)

    async def list_sets(self) -> list[TestSetRead]:
        return await self._set.list_sets()

    async def add_cases_to_set(self, set_id: str, case_ids: list[str]) -> TestSetRead:
        return await self._set.add_cases(set_id, case_ids)

    async def remove_cases_from_set(self, set_id: str, case_ids: list[str]) -> TestSetRead:
        return await self._set.remove_cases(set_id, case_ids)

    async def export_set(self, set_id: str) -> TestSetExport:
        return await self._set.export(set_id)
