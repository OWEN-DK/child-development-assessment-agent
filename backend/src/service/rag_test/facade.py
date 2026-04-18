import json
import os
import uuid
from datetime import datetime
from typing import Awaitable, Callable, Dict, List, Optional, Tuple

from jsonschema import ValidationError, validate

from src.config import settings
from src.constants.test_case import (TEST_CASE_DOMAINS,
                                     TEST_CASE_REQUIRED_FIELDS)
from src.core.database import db_session_factory
from src.models.test_case import (KnowledgeSnapshot, TestCase, TestCaseDraft,
                                  TestRun, TestSet as TestSetModel)
from src.schemas import (DifficultyLevel, DraftStatus, GenerationParams,
                         SourceDocument, TestDomain, TestResult, TestRunStatus)
from src.schemas.test_case import TestSet
from src.service.rag_test.draft_service import DraftService, draft_service
from src.service.rag_test.snapshot_service import (SnapshotService,
                                                   snapshot_service)
from src.service.rag_test.source_doc_service import (SourceDocService,
                                                     source_doc_service)
from src.service.rag_test.test_case_service import (TestCaseService,
                                                    test_case_service)
from src.service.rag_test.test_run_service import (TestRunService,
                                                   test_run_service)
from src.service.rag_test.test_set_service import (TestSetService,
                                                   test_set_service)
from src.utils.logger import logger

TEST_CASE_IMPORT_SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "required": TEST_CASE_REQUIRED_FIELDS,
        "properties": {
            "query": {"type": "string", "minLength": 1},
            "age": {"type": "integer", "minimum": 0, "maximum": 18},
            "domain": {"type": "string", "enum": TEST_CASE_DOMAINS + ["未知"]},
            "expected_knowledge_ids": {"type": "array", "items": {"type": "string"}},
            "expected_keywords": {"type": "array", "items": {"type": "string"}},
            "description": {"type": "string"},
            "answer_points": {"type": "array", "items": {"type": "string"}},
            "professional_terms": {"type": "array", "items": {"type": "string"}},
            "age_requirement": {"type": "string"},
        },
        "additionalProperties": False,
    },
}


class RagTestFacade:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(RagTestFacade, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self.test_case_service = test_case_service
        self.test_run_service = test_run_service
        self.draft_service = draft_service
        self.test_set_service = test_set_service
        self.snapshot_service = snapshot_service
        self.source_doc_service = source_doc_service
        self.db_session_factory = db_session_factory

        STORAGE_DIR = settings.rag_storage_dir
        self.test_runs_dir = f"{STORAGE_DIR}/test_runs"
        os.makedirs(self.test_runs_dir, exist_ok=True)

        self._initialized = True

    async def create_test_run(
        self,
        name: str,
        description: str = None,
        test_case_ids: list[str] = None,
        test_set_id: str = None,
    ) -> str:
        return await self.test_run_service.create_test_run(
            name, description, test_case_ids, test_set_id
        )

    async def add_test_case(self, test_case: TestCase) -> TestCase:
        return await self.test_case_service.create(test_case)

    async def execute_test_case(
        self,
        run_id: str,
        test_case: TestCase,
        progress_callback: Optional[Callable] = None,
    ) -> "src.models.test_case.TestRunResult":
        return await self.test_run_service.execute_test_case(
            run_id, test_case, progress_callback
        )

    async def complete_test_run(self, run_id: str):
        return await self.test_run_service.complete_test_run(run_id)

    async def execute_batch(
        self,
        run_id: str,
        concurrency: int = 5,
        progress_callback: Optional[Callable] = None,
    ) -> list:
        return await self.test_run_service.execute_batch(
            run_id, concurrency, progress_callback
        )

    async def update_test_case(
        self, test_case_id: str, test_case: TestCase
    ) -> Optional[TestCase]:
        return await self.test_case_service.update(test_case_id, test_case)

    async def delete_test_case(self, test_case_id: str) -> bool:
        return await self.test_case_service.delete(test_case_id)

    async def batch_delete_test_cases(self, case_ids: List[str]) -> int:
        return await self.test_case_service.batch_delete(case_ids)

    async def batch_delete_test_runs(self, run_ids: List[str]) -> int:
        from src.repository import TestRunRepository
        
        repo = TestRunRepository(self.db_session_factory)
        deleted_count = 0
        for run_id in run_ids:
            if await repo.delete(run_id):
                deleted_count += 1
                run_dir = f"{self.test_runs_dir}/{run_id}"
                if os.path.exists(run_dir):
                    import shutil
                    shutil.rmtree(run_dir)
                logger.info(f"Test run deleted: {run_id}")
        return deleted_count

    async def delete_draft(self, draft_id: str) -> bool:
        return await self.draft_service.delete_draft(draft_id)

    async def batch_delete_drafts(self, draft_ids: List[str]) -> int:
        return await self.draft_service.batch_delete_drafts(draft_ids)

    async def get_test_case(self, test_case_id: str) -> Optional[TestCase]:
        return await self.test_case_service.get(test_case_id)

    async def list_test_cases(self) -> List[TestCase]:
        return await self.test_case_service.list()

    async def analyze_test_run(self, run_id: str) -> dict:
        return await self.test_run_service.analyze_test_run(run_id)

    async def compare_test_runs(self, run_id_1: str, run_id_2: str) -> dict:
        return await self.test_run_service.compare_test_runs(run_id_1, run_id_2)

    async def recalculate_aggregate_scores(self):
        return await self.test_run_service.recalculate_aggregate_scores()

    async def preview_import_cases(
        self, import_data: List[dict]
    ) -> Tuple[List[dict], List[dict], List[dict]]:
        valid_cases = []
        invalid_cases = []
        duplicates = []

        try:
            validate(instance=import_data, schema=TEST_CASE_IMPORT_SCHEMA)
        except ValidationError as e:
            return (
                [],
                [
                    {
                        "index": 0,
                        "data": import_data[0] if import_data else {},
                        "error": str(e),
                    }
                ],
                [],
            )

        async def _get_existing():
            async with self.db_session_factory() as session:
                from sqlalchemy import select

                from src.models.test_case import TestCase
                stmt = select(TestCase)
                result = await session.execute(stmt)
                return list(result.scalars().all())

        existing_cases = await _get_existing()

        for i, case_data in enumerate(import_data):
            if case_data["age"] < 0 or case_data["age"] > 18:
                invalid_cases.append(
                    {
                        "index": i,
                        "data": case_data,
                        "error": f"年龄超出范围: {case_data['age']}，必须在0-18之间",
                    }
                )
                continue

            domain = case_data.get("domain", "未知")
            if domain not in [d.value for d in TestDomain] + ["未知"]:
                invalid_cases.append(
                    {
                        "index": i,
                        "data": case_data,
                        "error": f"无效的领域: {domain}，可选值: {[d.value for d in TestDomain]}",
                    }
                )
                continue

            duplicate_found = False
            for existing_case in existing_cases:
                if (
                    existing_case.query == case_data["query"]
                    and existing_case.age == case_data["age"]
                    and existing_case.domain.value == domain
                ):
                    duplicates.append(
                        {"index": i, "data": case_data, "existing_id": existing_case.id}
                    )
                    duplicate_found = True
                    break

            if not duplicate_found:
                valid_cases.append({"index": i, "data": case_data})

        return valid_cases, invalid_cases, duplicates

    async def batch_import_cases(
        self, cases_data: List[dict], test_set_id: Optional[str] = None
    ) -> Dict:
        test_cases = []
        for case_data in cases_data:
            try:
                if "domain" in case_data and isinstance(case_data["domain"], str):
                    if case_data["domain"] == "未知":
                        case_data["domain"] = TestDomain.SENSORY_INTEGRATION
                    else:
                        case_data["domain"] = TestDomain(case_data["domain"])

                test_case = TestCase(**case_data)
                if not test_case.id:
                    test_case.id = str(uuid.uuid4())
                test_cases.append(test_case)
            except Exception as e:
                raise ValueError(f"测试用例数据无效: {str(e)}")

        async def _import():
            async with self.db_session_factory() as session:
                from sqlalchemy import select

                from src.models.test_case import TestCase, TestSet, TestSetCase
                
                imported_ids = []
                try:
                    for test_case in test_cases:
                        stmt = select(TestCase).where(
                            TestCase.query == test_case.query,
                            TestCase.age == test_case.age,
                            TestCase.domain == test_case.domain,
                        )
                        result = await session.execute(stmt)
                        if result.scalar_one_or_none():
                            raise ValueError(
                                f"测试用例重复: {test_case.query} (age: {test_case.age}, domain: {test_case.domain.value})"
                            )

                    for test_case in test_cases:
                        session.add(test_case)
                        imported_ids.append(test_case.id)

                    if test_set_id:
                        test_set = await session.get(TestSet, test_set_id)
                        if test_set:
                            stmt = select(TestSetCase.test_case_id).where(
                                TestSetCase.test_set_id == test_set_id
                            )
                            result = await session.execute(stmt)
                            existing_ids = [row[0] for row in result.all()]

                            for case_id in imported_ids:
                                if case_id not in existing_ids:
                                    ts_case = TestSetCase(
                                        test_set_id=test_set_id, test_case_id=case_id
                                    )
                                    session.add(ts_case)

                    await session.commit()
                    return imported_ids
                except Exception as e:
                    await session.rollback()
                    raise e

        try:
            imported_ids = await _import()
            return {
                "imported_count": len(imported_ids),
                "failed_count": 0,
                "test_case_ids": imported_ids,
                "errors": [],
            }
        except Exception as e:
            raise e

    async def run_test_case(self, test_case: TestCase, limit: int = 10) -> TestResult:
        return await self.test_run_service.run_test_case(test_case, limit)

    async def run_all_tests(
        self, name: str = "", description: str = "", limit: int = 10
    ) -> TestRun:
        return await self.test_run_service.run_all_tests(name, description, limit)

    def list_test_runs(self) -> List[TestRun]:
        return self.test_run_service.list_test_runs()

    def get_test_run(self, run_id: str) -> Optional[TestRun]:
        return self.test_run_service.get_test_run(run_id)

    def create_snapshot(
        self, name: str = "", description: str = ""
    ) -> KnowledgeSnapshot:
        return self.snapshot_service.create_snapshot(name, description)

    def list_snapshots(self) -> List[KnowledgeSnapshot]:
        return self.snapshot_service.list_snapshots()

    def get_snapshot(self, snapshot_id: str) -> Optional[KnowledgeSnapshot]:
        return self.snapshot_service.get_snapshot(snapshot_id)

    def restore_snapshot(self, snapshot_id: str) -> bool:
        return self.snapshot_service.restore_snapshot(snapshot_id)

    def compare_config_versions(self, version_id1: str, version_id2: str) -> Dict:
        return self.test_run_service.compare_config_versions(version_id1, version_id2)

    def compare_test_runs(self, run_id1: str, run_id2: str) -> Dict:
        return self.test_run_service.compare_test_runs(run_id1, run_id2)

    async def upload_source_document(
        self, file_path: str, title: str, file_type: str
    ) -> SourceDocument:
        return await self.source_doc_service.upload_source_document(
            file_path, title, file_type
        )

    async def list_source_documents(self) -> List[SourceDocument]:
        return await self.source_doc_service.list_source_documents()

    async def get_source_document(self, doc_id: str) -> Optional[SourceDocument]:
        return await self.source_doc_service.get_source_document(doc_id)

    async def delete_source_document(self, doc_id: str) -> bool:
        return await self.source_doc_service.delete_source_document(doc_id)

    async def generate_test_case_drafts(
        self,
        source_document_id: str,
        params: GenerationParams,
        progress_callback: Optional[Callable[[int, int, str], Awaitable[None]]] = None,
    ) -> List[TestCaseDraft]:
        return await self.draft_service.generate_test_case_drafts(
            source_document_id, params, progress_callback
        )

    async def list_drafts(
        self, source_document_id: Optional[str] = None
    ) -> List[TestCaseDraft]:
        return await self.draft_service.list_drafts(source_document_id)

    async def get_draft(self, draft_id: str) -> Optional[TestCaseDraft]:
        return await self.draft_service.get_draft(draft_id)

    async def update_draft(
        self, draft_id: str, updates: Dict
    ) -> Optional[TestCaseDraft]:
        return await self.draft_service.update_draft(draft_id, updates)

    async def review_draft(self, draft_id: str, action: str) -> Optional[TestCaseDraft]:
        return await self.draft_service.review_draft(draft_id, action)

    async def import_reviewed_drafts(self, draft_ids: List[str]) -> Dict:
        return await self.draft_service.import_reviewed_drafts(draft_ids)

    async def create_test_set(
        self, name: str, description: str = "", source_type: str = "manual"
    ) -> TestSet:
        orm_set = await self.test_set_service.create_test_set(name, description, source_type)
        return TestSet(
            id=orm_set.id,
            name=orm_set.name,
            description=orm_set.description or "",
            source_type=orm_set.source_type.value if hasattr(orm_set.source_type, 'value') else str(orm_set.source_type),
            test_case_ids=[],
            created_at=orm_set.created_at,
            updated_at=orm_set.updated_at,
        )

    async def list_test_sets(self) -> List[TestSet]:
        orm_sets = await self.test_set_service.list_test_sets()
        return [
            TestSet(
                id=ts.id,
                name=ts.name,
                description=ts.description or "",
                source_type=ts.source_type.value if hasattr(ts.source_type, 'value') else str(ts.source_type),
                test_case_ids=[],
                created_at=ts.created_at,
                updated_at=ts.updated_at,
            )
            for ts in orm_sets
        ]

    async def get_test_set(self, test_set_id: str) -> Optional[TestSet]:
        orm_set = await self.test_set_service.get_test_set(test_set_id)
        if not orm_set:
            return None
        return TestSet(
            id=orm_set.id,
            name=orm_set.name,
            description=orm_set.description or "",
            source_type=orm_set.source_type.value if hasattr(orm_set.source_type, 'value') else str(orm_set.source_type),
            test_case_ids=getattr(orm_set, 'test_case_ids', []),
            created_at=orm_set.created_at,
            updated_at=orm_set.updated_at,
        )

    async def update_test_set(self, test_set_id: str, updates: Dict) -> Optional[TestSet]:
        orm_set = await self.test_set_service.update_test_set(test_set_id, updates)
        if not orm_set:
            return None
        return TestSet(
            id=orm_set.id,
            name=orm_set.name,
            description=orm_set.description or "",
            source_type=orm_set.source_type.value if hasattr(orm_set.source_type, 'value') else str(orm_set.source_type),
            test_case_ids=getattr(orm_set, 'test_case_ids', []),
            created_at=orm_set.created_at,
            updated_at=orm_set.updated_at,
        )

    async def delete_test_set(self, test_set_id: str) -> bool:
        return await self.test_set_service.delete_test_set(test_set_id)

    async def add_test_cases_to_set(
        self, test_set_id: str, case_ids: List[str]
    ) -> Optional[TestSet]:
        orm_set = await self.test_set_service.add_test_cases_to_set(test_set_id, case_ids)
        if not orm_set:
            return None
        return TestSet(
            id=orm_set.id,
            name=orm_set.name,
            description=orm_set.description or "",
            source_type=orm_set.source_type.value if hasattr(orm_set.source_type, 'value') else str(orm_set.source_type),
            test_case_ids=getattr(orm_set, 'test_case_ids', []),
            created_at=orm_set.created_at,
            updated_at=orm_set.updated_at,
        )

    async def remove_test_cases_from_set(
        self, test_set_id: str, case_ids: List[str]
    ) -> Optional[TestSet]:
        orm_set = await self.test_set_service.remove_test_cases_from_set(
            test_set_id, case_ids
        )
        if not orm_set:
            return None
        return TestSet(
            id=orm_set.id,
            name=orm_set.name,
            description=orm_set.description or "",
            source_type=orm_set.source_type.value if hasattr(orm_set.source_type, 'value') else str(orm_set.source_type),
            test_case_ids=getattr(orm_set, 'test_case_ids', []),
            created_at=orm_set.created_at,
            updated_at=orm_set.updated_at,
        )

    async def export_test_set(self, test_set_id: str) -> Optional[List[Dict]]:
        return await self.test_set_service.export_test_set(test_set_id)


rag_test_facade = RagTestFacade()


def get_rag_test_facade() -> RagTestFacade:
    return rag_test_facade
