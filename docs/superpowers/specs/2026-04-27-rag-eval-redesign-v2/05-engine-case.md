# 05 - CaseEngine 详细设计

## 需求

管理测试用例（TestCase）和测试集（TestSet）的全生命周期 CRUD，包括手动创建、JSON 批量导入导出、测试集用例增删。这是 v2 新增的独立引擎——v1 中这些逻辑分散在多个 service 和 controller 中。

## 当前问题

| 问题 | 位置 | 影响 |
|------|------|------|
| CRUD 逻辑散落 | `draft_service.py`、`controller.py` 各处 | 重复代码，职责不清 |
| 导入导出不统一 | `import_service.py`（部分实现） | 格式校验不完整 |
| 测试集管理耦合运行 | `test_executor.py` 混杂 | 无法独立操作测试集 |
| 无批量操作 | 逐个 API 调用 | 前端体验差 |

## 引擎架构

```
CaseEngineFacade (facade.py, ~150行)
  ├── CaseService (case_service.py, ~150行)
  └── SetService (set_service.py, ~120行)
```

## 组件设计

### CaseEngineFacade

```python
class CaseEngineFacade:
    """用例/测试集引擎门面"""

    def __init__(
        self,
        case_service: CaseService,
        set_service: SetService,
    ): ...

    # ── 测试用例 ──

    async def create_case(self, data: TestCaseCreate) -> TestCaseRead:
        """创建测试用例"""
        return await self._case_service.create(data)

    async def get_case(self, case_id: str) -> TestCaseRead:
        """获取测试用例"""
        return await self._case_service.get(case_id)

    async def update_case(self, case_id: str, data: TestCaseUpdate) -> TestCaseRead:
        """更新测试用例"""
        return await self._case_service.update(case_id, data)

    async def delete_case(self, case_id: str) -> None:
        """删除测试用例（级联删除 test_set_cases 关联）"""
        await self._case_service.delete(case_id)

    async def list_cases(
        self,
        page: int = 1,
        page_size: int = 20,
        domain: str | None = None,
        age_stage_label: str | None = None,
        source: str | None = None,
    ) -> TestCaseList:
        """分页查询测试用例"""
        return await self._case_service.list(page, page_size, domain, age_stage_label, source)

    async def batch_delete_cases(self, case_ids: list[str]) -> None:
        """批量删除测试用例"""
        await self._case_service.batch_delete(case_ids)

    async def import_from_json(self, data: TestCaseImportData) -> TestCaseList:
        """从 JSON 导入测试用例"""
        return await self._case_service.import_from_json(data)

    # ── 测试集 ──

    async def create_set(self, data: TestSetCreate) -> TestSetRead:
        """创建测试集"""
        return await self._set_service.create(data)

    async def get_set(self, set_id: str) -> TestSetRead:
        """获取测试集"""
        return await self._set_service.get(set_id)

    async def update_set(self, set_id: str, data: TestSetUpdate) -> TestSetRead:
        """更新测试集"""
        return await self._set_service.update(set_id, data)

    async def delete_set(self, set_id: str) -> None:
        """删除测试集（级联删除 test_set_cases 关联）"""
        await self._set_service.delete(set_id)

    async def list_sets(self) -> list[TestSetRead]:
        """列出所有测试集"""
        return await self._set_service.list()

    async def add_cases_to_set(self, set_id: str, case_ids: list[str]) -> TestSetRead:
        """向测试集添加用例"""
        return await self._set_service.add_cases(set_id, case_ids)

    async def remove_cases_from_set(self, set_id: str, case_ids: list[str]) -> TestSetRead:
        """从测试集移除用例"""
        return await self._set_service.remove_cases(set_id, case_ids)

    async def export_set(self, set_id: str) -> TestSetExport:
        """导出测试集为 JSON"""
        return await self._set_service.export(set_id)
```

### CaseService

```python
class CaseService:
    """测试用例 CRUD 服务"""

    def __init__(
        self,
        test_case_repository: TestCaseRepository,
        test_set_case_repository: TestSetCaseRepository,
        orm_mapper: OrmMapper,
    ): ...

    async def create(self, data: TestCaseCreate) -> TestCaseRead:
        """创建测试用例

        1. 自动计算 age_stage_label（从 age 推导）
        2. 设置 source = 'manual'
        3. 通过 repository 持久化
        4. 通过 orm_mapper 转换为 TestCaseRead
        """

    async def get(self, case_id: str) -> TestCaseRead:
        """获取测试用例，不存在抛 AppException(TEST_CASE_NOT_FOUND)"""

    async def update(self, case_id: str, data: TestCaseUpdate) -> TestCaseRead:
        """更新测试用例

        乐观锁：version 字段自增
        """

    async def delete(self, case_id: str) -> None:
        """删除测试用例

        级联删除 test_set_cases 中的关联记录。
        如果用例正在运行中（关联的 run 状态为 running），抛 RUN_IN_PROGRESS。
        """

    async def list(
        self,
        page: int,
        page_size: int,
        domain: str | None,
        age_stage_label: str | None,
        source: str | None,
    ) -> TestCaseList:
        """分页查询

        支持按 domain、age_stage_label、source 过滤。
        """

    async def batch_delete(self, case_ids: list[str]) -> None:
        """批量删除"""

    async def import_from_json(self, data: TestCaseImportData) -> TestCaseList:
        """从 JSON 批量导入

        流程：
        1. 校验每个 TestCaseImportItem 的必填字段（query, age, domain）
        2. 校验 domain 是否为合法 TestDomain 枚举值
        3. 批量创建，source 设为 'import'
        4. 自动计算 age_stage_label
        5. 返回创建结果列表

        允许导入重复文档（不抛 ValueError，返回已存在引用）。
        """
```

**Schema:**

```python
class TestCaseImportItem(BaseModel):
    """单个导入项，字段比 TestCaseCreate 更宽松"""
    query: str
    age: float                               # 岁，如 1.5
    domain: str                              # 字符串，校验时转为 TestDomain
    description: str | None = None
    expected_knowledge_ids: list[str] = []
    expected_keywords: list[str] = []
    answer_points_summary: str | None = None
    difficulty_level: str | None = None      # 校验时转为 DifficultyLevel

class TestCaseImportData(BaseModel):
    """批量导入请求"""
    cases: list[TestCaseImportItem]

class TestCaseUpdate(BaseModel):
    """测试用例更新"""
    query: str | None = None
    age: float | None = None
    domain: TestDomain | None = None
    description: str | None = None
    expected_knowledge_ids: list[str] | None = None
    expected_keywords: list[str] | None = None
    answer_points_summary: str | None = None
    difficulty_level: DifficultyLevel | None = None
```

### SetService

```python
class SetService:
    """测试集 CRUD 服务"""

    def __init__(
        self,
        test_set_repository: TestSetRepository,
        test_set_case_repository: TestSetCaseRepository,
        test_case_repository: TestCaseRepository,
        orm_mapper: OrmMapper,
    ): ...

    async def create(self, data: TestSetCreate) -> TestSetRead:
        """创建测试集

        1. 创建 test_sets 记录
        2. 若 case_ids 非空，批量创建 test_set_cases 关联
        3. 返回带 case_count 和 case_ids 的 TestSetRead
        """

    async def get(self, set_id: str) -> TestSetRead:
        """获取测试集，不存在抛 AppException(TEST_SET_NOT_FOUND)"""

    async def update(self, set_id: str, data: TestSetUpdate) -> TestSetRead:
        """更新测试集元数据（名称、描述）"""

    async def delete(self, set_id: str) -> None:
        """删除测试集

        仅删除 test_sets 和 test_set_cases 记录。
        不删除关联的 test_cases（用例独立存在）。
        """

    async def list(self) -> list[TestSetRead]:
        """列出所有测试集，带 case_count"""

    async def add_cases(self, set_id: str, case_ids: list[str]) -> TestSetRead:
        """向测试集添加用例

        1. 验证 set_id 存在
        2. 验证所有 case_id 存在
        3. 忽略已存在的关联（幂等）
        4. 批量插入 test_set_cases
        """

    async def remove_cases(self, set_id: str, case_ids: list[str]) -> TestSetRead:
        """从测试集移除用例

        仅删除 test_set_cases 关联，不删除 test_cases 本身。
        """

    async def export(self, set_id: str) -> TestSetExport:
        """导出测试集为 JSON

        返回包含测试集元数据和所有关联用例完整信息的 JSON 结构。
        用于跨系统迁移或备份。
        """
```

**Schema:**

```python
class TestSetExport(BaseModel):
    """测试集导出格式"""
    name: str
    description: str
    source_type: str
    exported_at: datetime
    cases: list[TestCaseRead]
```

## API 端点

| 端点 | 方法 | 功能 | 请求体 | 响应 |
|------|------|------|--------|------|
| `/rag/eval/test-cases` | GET | 列出测试用例 | Query: page, page_size, domain, age_stage_label, source | `APIResponse[TestCaseList]` |
| `/rag/eval/test-cases` | POST | 创建测试用例 | `TestCaseCreate` | `APIResponse[TestCaseRead]` |
| `/rag/eval/test-cases/{id}` | GET | 获取测试用例 | - | `APIResponse[TestCaseRead]` |
| `/rag/eval/test-cases/{id}` | PUT | 更新测试用例 | `TestCaseUpdate` | `APIResponse[TestCaseRead]` |
| `/rag/eval/test-cases/{id}` | DELETE | 删除测试用例 | - | `APIResponse[None]` |
| `/rag/eval/test-cases/batch` | DELETE | 批量删除 | `{case_ids: list[str]}` | `APIResponse[None]` |
| `/rag/eval/test-cases/import` | POST | JSON 导入 | `TestCaseImportData` | `APIResponse[TestCaseList]` |
| `/rag/eval/test-sets` | GET | 列出测试集 | - | `APIResponse[list[TestSetRead]]` |
| `/rag/eval/test-sets` | POST | 创建测试集 | `TestSetCreate` | `APIResponse[TestSetRead]` |
| `/rag/eval/test-sets/{id}` | GET | 获取测试集 | - | `APIResponse[TestSetRead]` |
| `/rag/eval/test-sets/{id}` | PUT | 更新测试集 | `TestSetUpdate` | `APIResponse[TestSetRead]` |
| `/rag/eval/test-sets/{id}` | DELETE | 删除测试集 | - | `APIResponse[None]` |
| `/rag/eval/test-sets/{id}/cases` | POST | 添加用例 | `{case_ids: list[str]}` | `APIResponse[TestSetRead]` |
| `/rag/eval/test-sets/{id}/cases` | DELETE | 移除用例 | `{case_ids: list[str]}` | `APIResponse[TestSetRead]` |
| `/rag/eval/test-sets/{id}/export` | GET | 导出测试集 | - | `APIResponse[TestSetExport]` |

## 错误码

> 以 `11-api-and-errors.md` 为准。

| 数字码 | 错误码 | HTTP | 触发场景 |
|--------|--------|------|----------|
| 13002 | `TEST_CASE_NOT_FOUND` | 404 | 用例 ID 不存在 |
| 13003 | `TEST_SET_NOT_FOUND` | 404 | 测试集 ID 不存在 |
| 13016 | `INVALID_TEST_CASE_FORMAT` | 400 | 导入数据字段校验失败 |
| 13017 | `INVALID_IMPORT_DATA` | 400 | 导入 JSON 格式错误 |
| 13020 | `RUN_IN_PROGRESS` | 409 | 删除运行中的用例 |

## 验收标准

1. `facade.py` ≤ 150 行，`case_service.py` ≤ 150 行，`set_service.py` ≤ 120 行
2. `CaseService.create` 自动计算 `age_stage_label`，调用共享工具函数 `utils/age_stage.py:calculate_age_stage_label(age: float) -> str`（DraftEngine 也使用此函数，不重复定义）
3. `import_from_json` 校验 `domain` 为合法 `TestDomain` 枚举值（使用 `values_callable` 映射）
4. `import_from_json` 允许重复文档上传（幂等，不抛 `ValueError`）
5. `SetService.add_cases` 幂等——已存在的关联不报错
6. `SetService.delete` 不删除关联的 `test_cases`（仅删 `test_set_cases`）
7. `TestSetRead.case_count` 从 `test_set_cases` 聚合查询，非冗余存储
8. 导出格式 `TestSetExport` 包含完整用例信息，可反序列化为 `TestCaseImportData` 往返无损
9. 所有 ORM→Pydantic 转换通过 `OrmMapper`，无手动序列化
10. `CaseEngineFacade` 通过 `RagEvalModule` DI 注入
11. 所有异常使用 `AppException`，错误码定义完整
12. 无硬编码值，无 `Singleton.__new__`
