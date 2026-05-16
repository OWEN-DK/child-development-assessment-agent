"""测试用例管理服务"""
import uuid
from typing import Optional

from sqlalchemy.ext.asyncio import async_sessionmaker

from src.models.rag_eval.test_case import TestCase
from src.repository.rag_eval.test_case_repo import TestCaseRepository
from src.schemas.rag_eval.test_case import (
    CreateTestCaseReq,
    TestCaseList,
    TestCaseRead,
    UpdateTestCaseReq,
)
from src.utils.logger import logger


class TestCaseService:
    """测试用例管理服务"""

    def __init__(self, session_factory: async_sessionmaker):
        self._session_factory = session_factory
        self._repo = TestCaseRepository(session_factory)

    async def list_cases(
        self,
        tenant_id: str,
        page: int = 1,
        page_size: int = 20,
        source: Optional[str] = None,
        difficulty: Optional[str] = None,
        search: Optional[str] = None,
    ) -> TestCaseList:
        """分页查询测试用例"""
        items, total = await self._repo.list_cases(
            tenant_id=tenant_id,
            page=page,
            page_size=page_size,
            source=source,
            difficulty=difficulty,
            search=search,
        )
        return TestCaseList(
            items=[self._to_read(item) for item in items],
            total=total,
        )

    async def get_case(self, tenant_id: str, case_id: str) -> TestCaseRead:
        """获取单个测试用例"""
        case = await self._repo.get_by_id(case_id, tenant_id)
        if not case:
            raise ValueError(f"测试用例不存在: {case_id}")
        return self._to_read(case)

    async def create_case(self, tenant_id: str, data: CreateTestCaseReq) -> TestCaseRead:
        """创建测试用例"""
        case_id = self._generate_id()
        case_data = data.model_dump()
        case_data.update({
            "id": case_id,
            "tenant_id": tenant_id,
            "source": "manual",
            "version": 1,
        })
        # 枚举字段转为字符串
        if "difficulty_level" in case_data and case_data["difficulty_level"] is not None:
            case_data["difficulty_level"] = str(case_data["difficulty_level"])

        case = await self._repo.create(case_data)
        logger.info(f"测试用例创建成功: {case_id}")
        return self._to_read(case)

    async def update_case(
        self, tenant_id: str, case_id: str, data: UpdateTestCaseReq
    ) -> TestCaseRead:
        """更新测试用例"""
        update_data = data.model_dump(exclude_unset=True)
        if not update_data:
            return await self.get_case(tenant_id, case_id)

        if "difficulty_level" in update_data and update_data["difficulty_level"] is not None:
            update_data["difficulty_level"] = str(update_data["difficulty_level"])

        case = await self._repo.update(case_id, update_data, tenant_id)
        return self._to_read(case)

    async def delete_case(self, tenant_id: str, case_id: str) -> None:
        """删除测试用例"""
        deleted = await self._repo.delete(case_id, tenant_id)
        if not deleted:
            raise ValueError(f"测试用例不存在: {case_id}")
        logger.info(f"测试用例删除成功: {case_id}")

    async def batch_delete(self, tenant_id: str, case_ids: list[str]) -> None:
        """批量删除测试用例"""
        count = await self._repo.batch_delete(case_ids, tenant_id)
        logger.info(f"批量删除测试用例: 请求 {len(case_ids)} 个，实际删除 {count} 个")

    async def import_cases(
        self, tenant_id: str, cases: list[CreateTestCaseReq]
    ) -> list[TestCaseRead]:
        """批量导入测试用例"""
        result = []
        batch_data = []
        for case_data in cases:
            case_id = self._generate_id()
            d = case_data.model_dump()
            d.update({
                "id": case_id,
                "tenant_id": tenant_id,
                "source": "import",
                "version": 1,
            })
            if "difficulty_level" in d and d["difficulty_level"] is not None:
                d["difficulty_level"] = str(d["difficulty_level"])
            batch_data.append(d)

        # 批量写入，共享 session 减少往返
        async with self._session_factory() as session:
            objs = []
            for d in batch_data:
                obj = TestCase(**d)
                session.add(obj)
                objs.append(obj)
            await session.commit()
            # refresh 获取 DB 生成字段
            for obj in objs:
                await session.refresh(obj)
                result.append(self._to_read(obj))

        logger.info(f"批量导入测试用例: {len(result)} 个")
        return result

    def _generate_id(self) -> str:
        """生成唯一 ID"""
        return str(uuid.uuid4()).replace("-", "")[:24]

    def _to_read(self, case: TestCase) -> TestCaseRead:
        """ORM 模型转响应实体"""
        return TestCaseRead(
            id=case.id,
            tenant_id=case.tenant_id,
            query=case.query,
            description=case.description,
            expected_knowledge_ids=case.expected_knowledge_ids,
            expected_keywords=case.expected_keywords,
            answer_points_summary=case.answer_points_summary,
            difficulty_level=case.difficulty_level or "medium",
            professional_terms=case.professional_terms,
            relevance_scores=case.relevance_scores,
            relevant_domains=case.relevant_domains,
            expected_conflicts=case.expected_conflicts,
            source=case.source or "manual",
            source_draft_id=case.source_draft_id,
            version=case.version or 1,
            created_at=case.created_at,
            updated_at=case.updated_at,
        )
