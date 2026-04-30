"""测试集 CRUD 服务"""

from datetime import datetime, timezone

from src.models.rag_eval.enums import TestSourceType
from src.models.rag_eval.test_set_case import TestSetCase
from src.repository.rag_eval.test_case_repository import TestCaseRepository
from src.repository.rag_eval.test_set_case_repository import TestSetCaseRepository
from src.repository.rag_eval.test_set_repository import TestSetRepository
from src.schemas.rag_eval.test_case import TestCaseRead
from src.schemas.rag_eval.test_set import (
    TestSetCreate,
    TestSetExport,
    TestSetRead,
    TestSetUpdate,
)
from src.utils.exceptions import (
    AppException,
    TestSetNotFoundException,
)
from src.utils.id_generator import generate_id
from src.utils.orm_mapper import OrmMapper


class SetService:
    """测试集 CRUD 服务"""

    def __init__(
        self,
        test_set_repository: TestSetRepository,
        test_set_case_repository: TestSetCaseRepository,
        test_case_repository: TestCaseRepository,
        orm_mapper: OrmMapper,
    ):
        self._set_repo = test_set_repository
        self._set_case_repo = test_set_case_repository
        self._case_repo = test_case_repository
        self._mapper = orm_mapper

    async def create(self, data: TestSetCreate) -> TestSetRead:
        """创建测试集，若 case_ids 非空则批量创建关联"""
        set_id = generate_id()
        set_data = {
            "id": set_id,
            "name": data.name,
            "description": data.description,
            "source_type": TestSourceType.MANUAL.value,
        }
        await self._set_repo.create(set_data)

        if data.case_ids:
            for case_id in data.case_ids:
                try:
                    await self._set_case_repo.create({
                        "test_set_id": set_id,
                        "test_case_id": case_id,
                    })
                except Exception:
                    # 幂等：忽略重复关联
                    continue

        return await self._build_set_read(set_id)

    async def get(self, set_id: str) -> TestSetRead:
        """获取测试集，不存在抛 TestSetNotFoundException"""
        return await self._build_set_read(set_id, must_exist=True)

    async def update(self, set_id: str, data: TestSetUpdate) -> TestSetRead:
        """更新测试集元数据（名称、描述）"""
        orm_obj = await self._set_repo.get_by_id(set_id)
        if not orm_obj:
            raise TestSetNotFoundException(set_id)
        await self._set_repo.update(set_id, data.model_dump(exclude_none=True))
        return await self._build_set_read(set_id)

    async def delete(self, set_id: str) -> None:
        """删除测试集，仅删 set 和关联，不删 cases"""
        orm_obj = await self._set_repo.get_by_id(set_id)
        if not orm_obj:
            raise TestSetNotFoundException(set_id)
        # 删除所有关联
        set_cases = await self._set_case_repo.get_by_test_set(set_id)
        for sc in set_cases:
            await self._set_case_repo.delete(sc.id)
        await self._set_repo.delete(set_id)

    async def list_sets(self) -> list[TestSetRead]:
        """列出所有测试集，带 case_count"""
        orm_list = await self._set_repo.get_all(limit=1000)
        results = []
        for orm_obj in orm_list:
            results.append(await self._build_set_read(orm_obj.id))
        return results

    async def add_cases(self, set_id: str, case_ids: list[str]) -> TestSetRead:
        """向测试集添加用例，幂等（已存在的关联静默忽略）"""
        orm_obj = await self._set_repo.get_by_id(set_id)
        if not orm_obj:
            raise TestSetNotFoundException(set_id)

        for case_id in case_ids:
            # 验证用例存在
            case = await self._case_repo.get_by_id(case_id)
            if not case:
                continue
            try:
                await self._set_case_repo.create({
                    "test_set_id": set_id,
                    "test_case_id": case_id,
                })
            except Exception:
                # 幂等：忽略重复关联
                continue

        return await self._build_set_read(set_id)

    async def remove_cases(self, set_id: str, case_ids: list[str]) -> TestSetRead:
        """从测试集移除用例，仅删除关联，不删除 test_cases"""
        orm_obj = await self._set_repo.get_by_id(set_id)
        if not orm_obj:
            raise TestSetNotFoundException(set_id)

        for case_id in case_ids:
            await self._set_case_repo.remove_by_set_and_case(set_id, case_id)

        return await self._build_set_read(set_id)

    async def export(self, set_id: str) -> TestSetExport:
        """导出测试集为 JSON，返回包含完整用例信息的结构"""
        set_obj = await self._set_repo.get_by_id(set_id)
        if not set_obj:
            raise TestSetNotFoundException(set_id)

        set_cases = await self._set_case_repo.get_by_test_set(set_id)
        case_ids = [sc.test_case_id for sc in set_cases]

        case_reads = []
        for case_id in case_ids:
            case_orm = await self._case_repo.get_by_id(case_id)
            if case_orm:
                case_reads.append(self._mapper.to_read(case_orm, TestCaseRead))

        return TestSetExport(
            name=set_obj.name or "",
            description=set_obj.description or "",
            source_type=self._mapper.safe_enum_value(set_obj.source_type) or "",
            exported_at=datetime.now(timezone.utc),
            cases=case_reads,
        )

    async def _build_set_read(self, set_id: str, must_exist: bool = False) -> TestSetRead:
        """构建带 case_count 和 case_ids 的 TestSetRead"""
        orm_obj = await self._set_repo.get_by_id(set_id)
        if not orm_obj:
            if must_exist:
                raise TestSetNotFoundException(set_id)
            raise TestSetNotFoundException(set_id)

        set_cases = await self._set_case_repo.get_by_test_set(set_id)
        case_count = len(set_cases)
        case_ids = [sc.test_case_id for sc in set_cases]

        attrs = OrmMapper._extract_orm_attrs(orm_obj)
        transformed = {k: OrmMapper._transform_value(v) for k, v in attrs.items()}
        transformed["case_count"] = case_count
        transformed["case_ids"] = case_ids
        return TestSetRead.model_validate(transformed)
