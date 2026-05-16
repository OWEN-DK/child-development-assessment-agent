"""测试集管理服务"""
import uuid
from typing import Optional

from sqlalchemy.ext.asyncio import async_sessionmaker

from src.models.rag_eval.test_case import TestSet
from src.repository.rag_eval.test_set_repo import TestSetRepository
from src.schemas.rag_eval.test_set import (
    CreateTestSetReq,
    TestSetList,
    TestSetRead,
    UpdateTestSetReq,
)
from src.utils.logger import logger


class TestSetService:
    """测试集管理服务"""

    def __init__(self, session_factory: async_sessionmaker):
        self._session_factory = session_factory
        self._repo = TestSetRepository(session_factory)

    async def list_sets(
        self,
        tenant_id: str,
        page: int = 1,
        page_size: int = 20,
    ) -> TestSetList:
        """分页查询测试集"""
        items, total = await self._repo.list_sets(
            tenant_id=tenant_id,
            page=page,
            page_size=page_size,
        )
        return TestSetList(
            items=[self._to_read(item) for item in items],
            total=total,
        )

    async def get_set(self, tenant_id: str, set_id: str) -> TestSetRead:
        """获取单个测试集"""
        test_set = await self._repo.get_by_id(set_id, tenant_id)
        if not test_set:
            raise ValueError(f"测试集不存在: {set_id}")
        return self._to_read(test_set)

    async def create_set(
        self, tenant_id: str, owner_id: str, data: CreateTestSetReq
    ) -> TestSetRead:
        """创建测试集"""
        set_id = self._generate_id()
        set_data = {
            "id": set_id,
            "tenant_id": tenant_id,
            "name": data.name,
            "description": data.description,
            "source_type": "manual",
            "case_ids": data.case_ids,
            "visibility": data.visibility,
            "owner_id": owner_id,
        }

        test_set = await self._repo.create(set_data)
        logger.info(f"测试集创建成功: {set_id} ({data.name})")
        return self._to_read(test_set)

    async def update_set(
        self, tenant_id: str, set_id: str, data: UpdateTestSetReq
    ) -> TestSetRead:
        """更新测试集"""
        update_data = data.model_dump(exclude_unset=True)
        if not update_data:
            return await self.get_set(tenant_id, set_id)

        test_set = await self._repo.update(set_id, update_data, tenant_id)
        return self._to_read(test_set)

    async def delete_set(self, tenant_id: str, set_id: str) -> None:
        """删除测试集"""
        deleted = await self._repo.delete(set_id, tenant_id)
        if not deleted:
            raise ValueError(f"测试集不存在: {set_id}")
        logger.info(f"测试集删除成功: {set_id}")

    async def add_cases(self, tenant_id: str, set_id: str, case_ids: list[str]) -> None:
        """向测试集中添加用例"""
        # 先确认测试集存在
        test_set = await self._repo.get_by_id(set_id, tenant_id)
        if not test_set:
            raise ValueError(f"测试集不存在: {set_id}")
        await self._repo.add_cases(set_id, case_ids)
        logger.info(f"测试集 {set_id} 添加 {len(case_ids)} 个用例")

    async def remove_cases(
        self, tenant_id: str, set_id: str, case_ids: list[str]
    ) -> None:
        """从测试集中移除用例"""
        test_set = await self._repo.get_by_id(set_id, tenant_id)
        if not test_set:
            raise ValueError(f"测试集不存在: {set_id}")
        await self._repo.remove_cases(set_id, case_ids)
        logger.info(f"测试集 {set_id} 移除 {len(case_ids)} 个用例")

    def _generate_id(self) -> str:
        """生成唯一 ID"""
        return str(uuid.uuid4()).replace("-", "")[:24]

    def _to_read(self, test_set: TestSet) -> TestSetRead:
        """ORM 模型转响应实体"""
        case_count = len(test_set.case_ids) if test_set.case_ids else 0
        return TestSetRead(
            id=test_set.id,
            tenant_id=test_set.tenant_id,
            name=test_set.name,
            description=test_set.description,
            source_type=test_set.source_type or "manual",
            case_ids=test_set.case_ids,
            visibility=test_set.visibility or "public",
            owner_id=test_set.owner_id,
            created_at=test_set.created_at,
            case_count=case_count,
        )
