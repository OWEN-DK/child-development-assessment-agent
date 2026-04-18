import uuid
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.database import db_session_factory
from src.models.test_case import TestCase, TestRun, TestRunResult, TestSetCase
from src.schemas import TestRunStatus
from src.utils.logger import logger


class TestRunCreator:
    """测试运行创建器，负责创建新的测试运行记录"""

    def __init__(self):
        self.db_session_factory = db_session_factory

    async def create_test_run(
        self,
        name: str,
        description: str = None,
        test_case_ids: list[str] = None,
        test_set_id: str = None,
    ) -> str:
        """
        创建测试运行
        
        Args:
            name: 测试运行名称
            description: 描述
            test_case_ids: 指定测试用例ID列表
            test_set_id: 测试集ID
            
        Returns:
            测试运行ID
        """
        async with self.db_session_factory() as session:
            run_id = str(uuid.uuid4())

            if test_case_ids:
                test_cases = await self._get_test_cases_by_ids(session, test_case_ids)
            elif test_set_id:
                test_cases = await self._get_test_cases_by_set(session, test_set_id)
            else:
                test_cases = await self._get_all_test_cases(session)

            test_run = TestRun(
                id=run_id,
                name=name,
                description=description,
                total_test_cases=len(test_cases),
                passed_test_cases=0,
                status=TestRunStatus.RUNNING,
            )

            session.add(test_run)
            await session.commit()

            logger.info(f"测试运行已创建：{run_id}, 共 {len(test_cases)} 个用例")
            return run_id

    async def _get_test_cases_by_ids(
        self, session: AsyncSession, test_case_ids: list[str]
    ) -> List[TestCase]:
        """根据ID列表获取测试用例"""
        stmt = select(TestCase).where(TestCase.id.in_(test_case_ids))
        result = await session.execute(stmt)
        return result.scalars().all()

    async def _get_test_cases_by_set(
        self, session: AsyncSession, test_set_id: str
    ) -> List[TestCase]:
        """根据测试集ID获取测试用例"""
        stmt = (
            select(TestCase)
            .join(TestSetCase)
            .where(TestSetCase.test_set_id == test_set_id)
            .options(selectinload(TestSetCase.test_case))
        )
        result = await session.execute(stmt)
        return result.scalars().all()

    async def _get_all_test_cases(self, session: AsyncSession) -> List[TestCase]:
        """获取所有测试用例"""
        stmt = select(TestCase)
        result = await session.execute(stmt)
        return result.scalars().all()
