import uuid
from typing import Dict, List, Optional, Tuple

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import db_session_factory
from src.models.test_case import TestCase, TestSetCase
from src.repository import TestCaseRepository
from src.schemas import TestDomain
from src.utils.logger import logger


class TestCaseService:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(TestCaseService, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self.db_session_factory = db_session_factory
        self._initialized = True

    async def create(self, test_case: TestCase) -> TestCase:
        repo = TestCaseRepository(self.db_session_factory)
        case_data = {
            "id": test_case.id or str(uuid.uuid4()),
            "query": test_case.query,
            "age": test_case.age,
            "domain": test_case.domain,
            "description": test_case.description,
            "expected_knowledge_count": test_case.expected_knowledge_count,
            "answer_points_summary": test_case.answer_points_summary,
            "min_age_requirement": test_case.min_age_requirement,
            "max_age_requirement": test_case.max_age_requirement,
            "difficulty_level": test_case.difficulty_level,
            "expected_knowledge_ids": test_case.expected_knowledge_ids,
            "expected_keywords": test_case.expected_keywords,
            "professional_terms": test_case.professional_terms,
            "relevance_scores": test_case.relevance_scores,
            "source_document_id": test_case.source_document_id,
            "version": test_case.version,
        }
        created = await repo.create(case_data)
        logger.info(f"Test case added: {created.id}")
        return created

    async def update(self, test_case_id: str, test_case: TestCase) -> Optional[TestCase]:
        repo = TestCaseRepository(self.db_session_factory)
        existing = await repo.get_by_id(test_case_id)
        if not existing:
            return None

        update_data = {}
        for key, value in test_case.model_dump(exclude_unset=True).items():
            if hasattr(existing, key):
                update_data[key] = value
        
        from datetime import datetime
        update_data["updated_at"] = datetime.now()

        updated = await repo.update(test_case_id, update_data)
        logger.info(f"Test case updated: {test_case_id}")
        return updated

    async def delete(self, test_case_id: str) -> bool:
        repo = TestCaseRepository(self.db_session_factory)
        existing = await repo.get_by_id(test_case_id)
        if not existing:
            return False
        result = await repo.delete(test_case_id)
        if result:
            logger.info(f"Test case deleted: {test_case_id}")
        return result

    async def batch_delete(self, case_ids: List[str]) -> int:
        repo = TestCaseRepository(self.db_session_factory)
        deleted_count = 0
        for case_id in case_ids:
            if await repo.delete(case_id):
                deleted_count += 1
                logger.info(f"Test case deleted: {case_id}")
        return deleted_count

    async def get(self, test_case_id: str) -> Optional[TestCase]:
        repo = TestCaseRepository(self.db_session_factory)
        return await repo.get_by_id(test_case_id)

    async def list(self) -> List[TestCase]:
        repo = TestCaseRepository(self.db_session_factory)
        return await repo.get_all(limit=10000)


test_case_service = TestCaseService()
