"""测试用例 CRUD 服务"""

from sqlalchemy import desc, func, select

from src.core.database import async_session_factory
from src.models.rag_eval.enums import DifficultyLevel, TestDomain
from src.models.rag_eval.test_case import TestCase
from src.repository.rag_eval.test_case_repository import TestCaseRepository
from src.repository.rag_eval.test_set_case_repository import TestSetCaseRepository
from src.schemas.rag_eval.test_case import (
    TestCaseCreate,
    TestCaseImportData,
    TestCaseImportItem,
    TestCaseList,
    TestCaseRead,
    TestCaseUpdate,
)
from src.utils.age_stage import calculate_age_stage_label
from src.utils.exceptions import (
    AppException,
    TestCaseNotFoundException,
)
from src.utils.id_generator import generate_id
from src.utils.orm_mapper import OrmMapper


class CaseService:
    """测试用例 CRUD 服务"""

    def __init__(
        self,
        test_case_repository: TestCaseRepository,
        test_set_case_repository: TestSetCaseRepository,
        orm_mapper: OrmMapper,
    ):
        self._repo = test_case_repository
        self._set_case_repo = test_set_case_repository
        self._mapper = orm_mapper

    async def create(self, data: TestCaseCreate) -> TestCaseRead:
        """创建测试用例，自动计算 age_stage_label，source='manual'"""
        age_stage_label = calculate_age_stage_label(data.age) if data.age is not None else ""
        obj_data = data.model_dump()
        obj_data["id"] = generate_id()
        obj_data["age_stage_label"] = age_stage_label
        obj_data["source"] = "manual"
        orm_obj = await self._repo.create(obj_data)
        return self._mapper.to_read(orm_obj, TestCaseRead)

    async def get(self, case_id: str) -> TestCaseRead:
        """获取测试用例，不存在抛 TestCaseNotFoundException"""
        orm_obj = await self._repo.get_by_id(case_id)
        if not orm_obj:
            raise TestCaseNotFoundException(case_id)
        return self._mapper.to_read(orm_obj, TestCaseRead)

    async def update(self, case_id: str, data: TestCaseUpdate) -> TestCaseRead:
        """更新测试用例，乐观锁 version 自增"""
        orm_obj = await self._repo.get_by_id(case_id)
        if not orm_obj:
            raise TestCaseNotFoundException(case_id)
        update_data = data.model_dump(exclude_none=True)
        if "age" in update_data:
            if update_data["age"] is not None:
                update_data["age_stage_label"] = calculate_age_stage_label(update_data["age"])
            else:
                update_data["age_stage_label"] = ""
        update_data["version"] = (orm_obj.version or 0) + 1
        updated = await self._repo.update(case_id, update_data)
        return self._mapper.to_read(updated, TestCaseRead)

    async def delete(self, case_id: str) -> None:
        """删除测试用例，级联删除 test_set_cases 关联"""
        orm_obj = await self._repo.get_by_id(case_id)
        if not orm_obj:
            raise TestCaseNotFoundException(case_id)
        # 级联删除 test_set_cases 中的关联记录
        set_cases = await self._set_case_repo.get_by_test_case(case_id)
        for sc in set_cases:
            await self._set_case_repo.delete(sc.id)
        await self._repo.delete(case_id)

    async def list_cases(
        self,
        page: int,
        page_size: int,
        domain: str | None = None,
        age_stage_label: str | None = None,
        source: str | None = None,
    ) -> TestCaseList:
        """分页查询测试用例，支持 domain / age_stage_label / source 过滤"""
        async with async_session_factory() as session:
            base_query = select(TestCase)
            if domain:
                base_query = base_query.where(TestCase.domain == domain)
            if age_stage_label:
                base_query = base_query.where(TestCase.age_stage_label == age_stage_label)
            if source:
                base_query = base_query.where(TestCase.source == source)

            count_query = select(func.count()).select_from(base_query.subquery())
            total = (await session.execute(count_query)).scalar_one()

            query = base_query.order_by(desc(TestCase.created_at))
            query = query.offset((page - 1) * page_size).limit(page_size)
            result = await session.execute(query)
            items = list(result.scalars().all())

        return TestCaseList(
            items=self._mapper.to_read_list(items, TestCaseRead),
            total=total,
            page=page,
            page_size=page_size,
        )

    async def batch_delete(self, case_ids: list[str]) -> None:
        """批量删除测试用例，级联删除关联"""
        for case_id in case_ids:
            set_cases = await self._set_case_repo.get_by_test_case(case_id)
            for sc in set_cases:
                await self._set_case_repo.delete(sc.id)
            await self._repo.delete(case_id)

    async def import_from_json(self, data: TestCaseImportData) -> TestCaseList:
        """从 JSON 批量导入，校验 domain 为合法枚举值，允许重复上传"""
        created = []
        for item in data.cases:
            if not item.query:
                continue

            # 校验 domain 为合法 TestDomain 值（domain 可选，为 None 时跳过校验）
            domain_value = None
            if item.domain is not None:
                domain_value = _parse_enum(item.domain, TestDomain)
                if domain_value is None:
                    continue

            difficulty_value = None
            if item.difficulty_level:
                difficulty_value = _parse_enum(item.difficulty_level, DifficultyLevel)

            age_stage = calculate_age_stage_label(item.age) if item.age is not None else ""
            obj_data = {
                "id": generate_id(),
                "query": item.query,
                "age": item.age,
                "age_stage_label": age_stage,
                "domain": domain_value,
                "description": item.description,
                "expected_knowledge_ids": item.expected_knowledge_ids,
                "expected_keywords": item.expected_keywords,
                "answer_points_summary": item.answer_points_summary,
                "difficulty_level": difficulty_value,
                "source": "import",
            }
            try:
                orm_obj = await self._repo.create(obj_data)
                created.append(orm_obj)
            except Exception:
                # 允许重复上传，跳过冲突项继续处理其余项
                continue

        return TestCaseList(
            items=self._mapper.to_read_list(created, TestCaseRead),
            total=len(created),
            page=1,
            page_size=len(created),
        )


def _parse_enum(value: str, enum_cls) -> str | None:
    """将字符串解析为枚举的 .value，失败返回 None"""
    try:
        return enum_cls(value).value
    except ValueError:
        try:
            return enum_cls[value.upper()].value
        except (ValueError, KeyError):
            return None
