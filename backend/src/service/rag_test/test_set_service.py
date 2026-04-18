import uuid
from datetime import datetime
from typing import Dict, List, Optional

from sqlalchemy import select

from src.core.database import db_session_factory
from src.models.test_case import TestCase, TestSet, TestSetCase
from src.utils.logger import logger


class TestSetService:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(TestSetService, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self.db_session_factory = db_session_factory
        self._initialized = True

    async def create_test_set(
        self, name: str, description: str = "", source_type: str = "manual"
    ) -> TestSet:
        from src.schemas import TestSourceType
        
        async with self.db_session_factory() as session:
            test_set = TestSet(
                id=str(uuid.uuid4()),
                name=name,
                description=description,
                source_type=TestSourceType(source_type),
            )
            session.add(test_set)
            await session.commit()
            await session.refresh(test_set)
            logger.info(f"Test set created: {test_set.id} - {name}")
            return test_set

    async def list_test_sets(self) -> List[TestSet]:
        async with self.db_session_factory() as session:
            stmt = select(TestSet).order_by(TestSet.created_at.desc())
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def get_test_set(self, test_set_id: str) -> Optional[TestSet]:
        async with self.db_session_factory() as session:
            test_set = await session.get(TestSet, test_set_id)
            if test_set:
                stmt = select(TestSetCase.test_case_id).where(
                    TestSetCase.test_set_id == test_set_id
                )
                result = await session.execute(stmt)
                test_set.test_case_ids = [row[0] for row in result.all()]
            return test_set

    async def update_test_set(self, test_set_id: str, updates: Dict) -> Optional[TestSet]:
        async with self.db_session_factory() as session:
            test_set = await session.get(TestSet, test_set_id)
            if not test_set:
                return None

            for key, value in updates.items():
                if hasattr(test_set, key):
                    setattr(test_set, key, value)
            test_set.updated_at = datetime.now()

            await session.commit()
            await session.refresh(test_set)

            stmt = select(TestSetCase.test_case_id).where(
                TestSetCase.test_set_id == test_set_id
            )
            result = await session.execute(stmt)
            test_set.test_case_ids = [row[0] for row in result.all()]

            return test_set

    async def delete_test_set(self, test_set_id: str) -> bool:
        async with self.db_session_factory() as session:
            test_set = await session.get(TestSet, test_set_id)
            if not test_set:
                return False

            await session.delete(test_set)
            await session.commit()
            logger.info(f"Test set deleted: {test_set_id}")
            return True

    async def add_test_cases_to_set(
        self, test_set_id: str, case_ids: List[str]
    ) -> Optional[TestSet]:
        async with self.db_session_factory() as session:
            test_set = await session.get(TestSet, test_set_id)
            if not test_set:
                return None

            stmt = select(TestSetCase.test_case_id).where(
                TestSetCase.test_set_id == test_set_id
            )
            result = await session.execute(stmt)
            existing_ids = [row[0] for row in result.all()]

            for case_id in case_ids:
                if case_id not in existing_ids:
                    ts_case = TestSetCase(
                        test_set_id=test_set_id, test_case_id=case_id
                    )
                    session.add(ts_case)

            await session.commit()
            await session.refresh(test_set)

            stmt = select(TestSetCase.test_case_id).where(
                TestSetCase.test_set_id == test_set_id
            )
            result = await session.execute(stmt)
            test_set.test_case_ids = [row[0] for row in result.all()]

            return test_set

    async def remove_test_cases_from_set(
        self, test_set_id: str, case_ids: List[str]
    ) -> Optional[TestSet]:
        async with self.db_session_factory() as session:
            test_set = await session.get(TestSet, test_set_id)
            if not test_set:
                return None

            stmt = select(TestSetCase).where(
                TestSetCase.test_set_id == test_set_id,
                TestSetCase.test_case_id.in_(case_ids),
            )
            result = await session.execute(stmt)
            for ts_case in result.scalars().all():
                await session.delete(ts_case)

            await session.commit()
            await session.refresh(test_set)

            stmt = select(TestSetCase.test_case_id).where(
                TestSetCase.test_set_id == test_set_id
            )
            result = await session.execute(stmt)
            test_set.test_case_ids = [row[0] for row in result.all()]

            return test_set

    async def export_test_set(self, test_set_id: str) -> Optional[List[Dict]]:
        async with self.db_session_factory() as session:
            test_set = await session.get(TestSet, test_set_id)
            if not test_set:
                return None

            stmt = select(TestSetCase.test_case_id).where(
                TestSetCase.test_set_id == test_set_id
            )
            result = await session.execute(stmt)
            case_ids = [row[0] for row in result.all()]

            cases = []
            for case_id in case_ids:
                case = await session.get(TestCase, case_id)
                if case:
                    cases.append(case.model_dump())

            return cases


test_set_service = TestSetService()
