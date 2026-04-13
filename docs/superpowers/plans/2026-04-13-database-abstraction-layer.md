# 数据库操作抽象层 (DAL) 实现计划

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 封装所有通用数据库操作为统一的数据访问层，消除30个业务文件中的重复CRUD代码，提升可维护性和数据操作一致性。

**Architecture:** 基于泛型创建BaseRepository基类实现通用CRUD操作，每个ORM模型对应一个专属Repository类继承BaseRepository并实现模型特有方法。Repository内部管理session生命周期（接收session_factory而非单个session），所有业务层（服务/控制器/核心逻辑）通过DI容器获取Repository实例调用数据操作方法，不再直接操作SQLAlchemy Session对象。

**Tech Stack:** SQLAlchemy 2.0, Pydantic v2, Python 3.11+, Injector DI框架

**重要设计决策:**
- **Session管理**: Repository接收`async_session_factory`而非单个`AsyncSession`，每个方法内部通过`async with`创建独立session，避免并发请求的数据竞争
- **Schema策略**: 项目无`src/schemas/`目录，Repository的create/update方法直接接收`Dict[str, Any]`或ORM模型实例，由调用方负责数据校验
- **模型名称修正**: 使用实际ORM模型名称(`LLMCallLog`非`LLMLog`, `ABTestMetrics`非`ABTestMetric`, `DocumentRecord`非`DocumentChunk`)
- **兼容现有Config Repository**: 保留`src/config/core/repository.py`中的`MySQLConfigRepository`，新Repository层与之并存，逐步迁移

---

## 一、文件结构设计

| 操作 | 文件路径 | 职责 |
|------|----------|------|
| 创建 | `src/repository/__init__.py` | Repository层导出入口 |
| 创建 | `src/repository/base.py` | 泛型BaseRepository基类，实现通用CRUD |
| 创建 | `src/repository/config_repository.py` | 配置模型专属Repository |
| 创建 | `src/repository/document_repository.py` | 文档模型专属Repository |
| 创建 | `src/repository/test_case_repository.py` | 测试用例模型专属Repository |
| 创建 | `src/repository/prompt_repository.py` | 提示词模型专属Repository |
| 创建 | `src/repository/monitor_repository.py` | 监控模型专属Repository |
| 创建 | `src/model/schemas/repository_schemas.py` | Repository专用Pydantic schemas（可选） |
| 修改 | `src/core/di_container.py` | 注册所有Repository到DI容器 |
| 修改 | 30个业务文件 | 分阶段迁移直接Session操作为Repository调用 |

**注意**: 路径已移除`backend/`前缀，以项目根目录为基准。

---

## 二、任务分解

### Task 1: 实现BaseRepository通用基类

**Files:**
- Create: `src/repository/base.py`
- Test: `tests/repository/test_base.py`

- [ ] **Step 1: 编写BaseRepository基类代码**

```python
from typing import TypeVar, Generic, List, Optional, Any, Dict
from sqlalchemy import select, update, delete
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.ext.asyncio import async_sessionmaker

ModelType = TypeVar("ModelType", bound=DeclarativeBase)

class BaseRepository(Generic[ModelType]):
    """通用CRUD Repository基类
    
    设计要点:
    - 接收session_factory而非单个session，避免并发数据竞争
    - 每个方法内部管理session生命周期
    - 过滤查询时校验字段有效性，防止SQL注入
    """
    
    def __init__(self, model: type[ModelType], db_session_factory: async_sessionmaker):
        self.model = model
        self.db_session_factory = db_session_factory

    async def get_by_id(self, id: Any) -> Optional[ModelType]:
        """根据ID查询单个记录"""
        async with self.db_session_factory() as session:
            result = await session.execute(select(self.model).where(self.model.id == id))
            return result.scalar_one_or_none()

    async def get_all(self, skip: int = 0, limit: int = 100, order_by: Optional[Any] = None) -> List[ModelType]:
        """查询所有记录，支持分页和排序"""
        async with self.db_session_factory() as session:
            query = select(self.model).offset(skip).limit(limit)
            if order_by:
                query = query.order_by(order_by)
            result = await session.execute(query)
            return list(result.scalars().all())

    async def create(self, obj_data: Dict[str, Any]) -> ModelType:
        """创建新记录
        
        Args:
            obj_data: 字典格式的数据，由调用方负责校验
        """
        async with self.db_session_factory() as session:
            db_obj = self.model(**obj_data)
            session.add(db_obj)
            await session.commit()
            await session.refresh(db_obj)
            return db_obj

    async def update(self, obj_id: Any, obj_data: Dict[str, Any]) -> ModelType:
        """更新现有记录
        
        Args:
            obj_id: 记录ID
            obj_data: 要更新的字段字典
        """
        async with self.db_session_factory() as session:
            # 先查询再更新，避免merge()跨session的副作用
            result = await session.execute(select(self.model).where(self.model.id == obj_id))
            db_obj = result.scalar_one_or_none()
            if db_obj is None:
                raise ValueError(f"{self.model.__name__} with id={obj_id} not found")
            for field, value in obj_data.items():
                setattr(db_obj, field, value)
            await session.commit()
            await session.refresh(db_obj)
            return db_obj

    async def delete(self, id: Any) -> bool:
        """根据ID删除记录"""
        async with self.db_session_factory() as session:
            result = await session.execute(delete(self.model).where(self.model.id == id))
            await session.commit()
            return result.rowcount > 0

    async def get_by_filter(self, skip: int = 0, limit: int = 100, order_by: Optional[Any] = None, **filters) -> List[ModelType]:
        """根据过滤条件查询多条记录
        
        Args:
            skip: 分页偏移
            limit: 分页限制
            order_by: 排序字段
            **filters: 过滤条件，字段名必须是模型的有效属性
        """
        async with self.db_session_factory() as session:
            query = select(self.model)
            for field, value in filters.items():
                if not hasattr(self.model, field):
                    raise ValueError(f"Invalid filter field '{field}' for model {self.model.__name__}")
                query = query.where(getattr(self.model, field) == value)
            
            if order_by:
                query = query.order_by(order_by)
            query = query.offset(skip).limit(limit)
            
            result = await session.execute(query)
            return list(result.scalars().all())

    async def get_one_by_filter(self, **filters) -> Optional[ModelType]:
        """根据过滤条件查询单个记录"""
        async with self.db_session_factory() as session:
            query = select(self.model)
            for field, value in filters.items():
                if not hasattr(self.model, field):
                    raise ValueError(f"Invalid filter field '{field}' for model {self.model.__name__}")
                query = query.where(getattr(self.model, field) == value)
            
            result = await session.execute(query)
            return result.scalar_one_or_none()

    async def count_by_filter(self, **filters) -> int:
        """根据过滤条件统计记录数"""
        from sqlalchemy import func
        async with self.db_session_factory() as session:
            query = select(func.count()).select_from(self.model)
            for field, value in filters.items():
                if not hasattr(self.model, field):
                    raise ValueError(f"Invalid filter field '{field}' for model {self.model.__name__}")
                query = query.where(getattr(self.model, field) == value)
            
            result = await session.execute(query)
            return result.scalar_one()
```

- [ ] **Step 2: 编写测试用例**

**注意**: 使用SQLite内存数据库测试，避免MySQL特有类型(DECIMAL等)的兼容性问题。测试模型使用简单类型。

```python
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from src.repository.base import BaseRepository

pytestmark = pytest.mark.asyncio

# 测试用模型（使用SQLite兼容类型）
class Base(DeclarativeBase):
    pass

class TestModel(Base):
    __tablename__ = "test_models"
    id: Mapped[str] = mapped_column(primary_key=True)
    name: Mapped[str]
    value: Mapped[int]

@pytest_asyncio.fixture
async def db_session_factory():
    """创建测试用session factory"""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()

async def test_base_repository_crud(db_session_factory):
    repo = BaseRepository[TestModel](TestModel, db_session_factory)
    
    # 测试创建
    obj = await repo.create({"id": "test_1", "name": "test", "value": 100})
    assert obj.id == "test_1"
    assert obj.name == "test"
    
    # 测试ID查询
    obj_by_id = await repo.get_by_id("test_1")
    assert obj_by_id is not None
    assert obj_by_id.value == 100
    
    # 测试更新（通过ID而非对象）
    updated_obj = await repo.update("test_1", {"value": 200})
    assert updated_obj.value == 200
    
    # 测试更新不存在的记录
    with pytest.raises(ValueError, match="not found"):
        await repo.update("nonexistent", {"value": 300})
    
    # 测试过滤查询
    filtered_objs = await repo.get_by_filter(name="test")
    assert len(filtered_objs) == 1
    
    # 测试无效字段过滤
    with pytest.raises(ValueError, match="Invalid filter field"):
        await repo.get_by_filter(invalid_field="test")
    
    # 测试删除
    delete_result = await repo.delete("test_1")
    assert delete_result is True
    deleted_obj = await repo.get_by_id("test_1")
    assert deleted_obj is None

async def test_base_repository_pagination(db_session_factory):
    repo = BaseRepository[TestModel](TestModel, db_session_factory)
    
    # 创建多条记录
    for i in range(5):
        await repo.create({"id": f"test_{i}", "name": "batch", "value": i})
    
    # 测试分页
    page1 = await repo.get_by_filter(skip=0, limit=2, name="batch")
    assert len(page1) == 2
    
    page2 = await repo.get_by_filter(skip=2, limit=2, name="batch")
    assert len(page2) == 2
    
    # 测试计数
    count = await repo.count_by_filter(name="batch")
    assert count == 5

async def test_base_repository_get_all_with_ordering(db_session_factory):
    repo = BaseRepository[TestModel](TestModel, db_session_factory)
    
    # 创建无序记录
    for i in [3, 1, 4, 1, 5]:
        await repo.create({"id": f"test_{i}", "name": "order_test", "value": i})
    
    # 测试升序
    from sqlalchemy import asc
    asc_results = await repo.get_all(order_by=asc(TestModel.value))
    assert [r.value for r in asc_results] == [1, 1, 3, 4, 5]
    
    # 测试降序
    from sqlalchemy import desc
    desc_results = await repo.get_all(order_by=desc(TestModel.value))
    assert [r.value for r in desc_results] == [5, 4, 3, 1, 1]
```

- [ ] **Step 3: 运行测试验证通过**

```bash
cd /Users/owen/project/ai/child-development-assessment-agent
pytest tests/repository/test_base.py -v
```
Expected: All tests pass

---

### Task 2: 实现各模型专属Repository类

**Files:**
- Create: `src/repository/config_repository.py`
- Create: `src/repository/document_repository.py`
- Create: `src/repository/test_case_repository.py`
- Create: `src/repository/prompt_repository.py`
- Create: `src/repository/monitor_repository.py`
- Create: `src/repository/__init__.py`

**重要说明:**
- 所有Repository继承`BaseRepository[ModelType]`，不再使用Schema泛型参数
- create/update方法接收`Dict[str, Any]`，由调用方（服务层/控制器）负责数据校验
- 模型名称使用实际ORM定义: `LLMCallLog` (非`LLMLog`), `ABTestMetrics` (非`ABTestMetric`), `DocumentRecord` (非`DocumentChunk`)

- [ ] **Step 1: 编写ConfigRepository**

**重要**: `ConfigVersion`模型没有`key`字段（只有`id`, `created_at`, `created_by`, `description`, `config_snapshot`, `parent_version_id`, `is_factory_reset`）。获取最新版本直接按时间排序取最新。

**与现有MySQLConfigRepository的关系**: 
- 现有`src/config/core/repository.py`中的`MySQLConfigRepository`操作的是实体对象(ConfigVersionEntity)和字典，接口面向ConfigManager业务逻辑
- 新`ConfigVersionRepository`直接操作ORM模型，提供通用CRUD
- 两者并存：ConfigManager继续使用MySQLConfigRepository（后续可逐步重构），新Repository供其他模块使用

```python
from typing import Optional, List
from sqlalchemy import select, desc, or_
from sqlalchemy.ext.asyncio import async_sessionmaker
from src.repository.base import BaseRepository
from src.models.config import ConfigVersion, ConfigAuditLog

class ConfigVersionRepository(BaseRepository[ConfigVersion]):
    def __init__(self, db_session_factory: async_sessionmaker):
        super().__init__(ConfigVersion, db_session_factory)
    
    async def get_latest_version(self) -> Optional[ConfigVersion]:
        """获取最新配置版本（按创建时间排序）
        
        注意: ConfigVersion没有key字段，直接取最新版本
        """
        async with self.db_session_factory() as session:
            result = await session.execute(
                select(ConfigVersion)
                .order_by(desc(ConfigVersion.created_at))
                .limit(1)
            )
            return result.scalar_one_or_none()
    
    async def get_version_history(self, skip: int = 0, limit: int = 20) -> List[ConfigVersion]:
        """获取配置版本历史"""
        return await self.get_by_filter(
            skip=skip, limit=limit, order_by=desc(ConfigVersion.created_at)
        )
    
    async def get_by_parent_version(self, parent_version_id: str) -> List[ConfigVersion]:
        """获取指定父版本的子版本"""
        return await self.get_by_filter(parent_version_id=parent_version_id)

class ConfigAuditLogRepository(BaseRepository[ConfigAuditLog]):
    def __init__(self, db_session_factory: async_sessionmaker):
        super().__init__(ConfigAuditLog, db_session_factory)
    
    async def get_logs_by_version(self, version_id: str) -> List[ConfigAuditLog]:
        """获取指定版本相关的审计日志（包含from_version和to_version）"""
        async with self.db_session_factory() as session:
            from sqlalchemy import or_
            result = await session.execute(
                select(ConfigAuditLog)
                .where(
                    or_(
                        ConfigAuditLog.from_version == version_id,
                        ConfigAuditLog.to_version == version_id
                    )
                )
                .order_by(desc(ConfigAuditLog.timestamp))
            )
            return list(result.scalars().all())
    
    async def get_logs_by_action(self, action: str, skip: int = 0, limit: int = 50) -> List[ConfigAuditLog]:
        """根据操作类型获取审计日志"""
        return await self.get_by_filter(skip=skip, limit=limit, order_by=desc(ConfigAuditLog.timestamp), action=action)
```

- [ ] **Step 2: 编写DocumentRepository**

```python
from typing import Optional, List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker
from src.repository.base import BaseRepository
from src.models.document import SourceDocument, DocumentRecord

class SourceDocumentRepository(BaseRepository[SourceDocument]):
    def __init__(self, db_session_factory: async_sessionmaker):
        super().__init__(SourceDocument, db_session_factory)
    
    async def get_by_file_hash(self, file_hash: str) -> Optional[SourceDocument]:
        """根据文件哈希查询文档"""
        return await self.get_one_by_filter(file_hash=file_hash)
    
    async def get_by_status(self, status: str, skip: int = 0, limit: int = 50) -> List[SourceDocument]:
        """根据状态查询文档"""
        return await self.get_by_filter(skip=skip, limit=limit, status=status)

class DocumentRecordRepository(BaseRepository[DocumentRecord]):
    def __init__(self, db_session_factory: async_sessionmaker):
        super().__init__(DocumentRecord, db_session_factory)
    
    async def get_by_file_hash(self, file_hash: str) -> Optional[DocumentRecord]:
        """根据文件哈希查询文档记录"""
        return await self.get_one_by_filter(file_hash=file_hash)
```

- [ ] **Step 3: 编写TestCaseRepository**

```python
from typing import Optional, List
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import async_sessionmaker
from src.repository.base import BaseRepository
from src.models.test_case import TestCase, TestCaseDraft, TestSet, TestSetCase, TestRun, TestRunResult

class TestCaseRepository(BaseRepository[TestCase]):
    def __init__(self, db_session_factory: async_sessionmaker):
        super().__init__(TestCase, db_session_factory)
    
    async def get_by_domain(self, domain: str, skip: int = 0, limit: int = 50) -> List[TestCase]:
        """根据领域查询测试用例"""
        return await self.get_by_filter(skip=skip, limit=limit, domain=domain)
    
    async def get_by_age_range(self, age_min: float, age_max: float) -> List[TestCase]:
        """根据年龄范围查询测试用例"""
        async with self.db_session_factory() as session:
            result = await session.execute(
                select(TestCase).where(TestCase.age >= age_min, TestCase.age <= age_max)
            )
            return list(result.scalars().all())

class TestCaseDraftRepository(BaseRepository[TestCaseDraft]):
    def __init__(self, db_session_factory: async_sessionmaker):
        super().__init__(TestCaseDraft, db_session_factory)
    
    async def get_by_status(self, status: str, skip: int = 0, limit: int = 50) -> List[TestCaseDraft]:
        """根据状态查询草稿"""
        return await self.get_by_filter(skip=skip, limit=limit, status=status)
    
    async def get_by_source_document(self, source_document_id: str) -> List[TestCaseDraft]:
        """根据源文档ID查询草稿"""
        return await self.get_by_filter(source_document_id=source_document_id)

class TestSetRepository(BaseRepository[TestSet]):
    def __init__(self, db_session_factory: async_sessionmaker):
        super().__init__(TestSet, db_session_factory)

class TestSetCaseRepository(BaseRepository[TestSetCase]):
    def __init__(self, db_session_factory: async_sessionmaker):
        super().__init__(TestSetCase, db_session_factory)
    
    async def get_cases_by_test_set(self, test_set_id: str) -> List[TestSetCase]:
        """获取测试集的所有用例关联"""
        return await self.get_by_filter(test_set_id=test_set_id)
    
    async def get_test_sets_by_case(self, test_case_id: str) -> List[TestSetCase]:
        """反向查询：获取包含指定用例的所有测试集"""
        return await self.get_by_filter(test_case_id=test_case_id)
    
    async def add_case_to_set(self, test_set_id: str, test_case_id: str) -> TestSetCase:
        """添加用例到测试集"""
        return await self.create({
            "test_set_id": test_set_id,
            "test_case_id": test_case_id
        })
    
    async def remove_case_from_set(self, test_set_id: str, test_case_id: str) -> bool:
        """从测试集移除用例"""
        async with self.db_session_factory() as session:
            from sqlalchemy import delete
            result = await session.execute(
                delete(TestSetCase).where(
                    TestSetCase.test_set_id == test_set_id,
                    TestSetCase.test_case_id == test_case_id
                )
            )
            await session.commit()
            return result.rowcount > 0
    
    async def get_test_cases_by_set_id(self, test_set_id: str) -> List["TestCase"]:
        """通过JOIN查询获取测试集的所有测试用例
        
        注意: TestCase和TestSet通过TestSetCase中间表关联，不能直接过滤
        """
        async with self.db_session_factory() as session:
            result = await session.execute(
                select(TestCase)
                .join(TestSetCase, TestCase.id == TestSetCase.test_case_id)
                .where(TestSetCase.test_set_id == test_set_id)
            )
            return list(result.scalars().all())

class TestRunRepository(BaseRepository[TestRun]):
    def __init__(self, db_session_factory: async_sessionmaker):
        super().__init__(TestRun, db_session_factory)
    
    async def get_latest_runs(self, limit: int = 10) -> List[TestRun]:
        """获取最近的测试运行"""
        return await self.get_all(skip=0, limit=limit, order_by=desc(TestRun.created_at))

class TestRunResultRepository(BaseRepository[TestRunResult]):
    def __init__(self, db_session_factory: async_sessionmaker):
        super().__init__(TestRunResult, db_session_factory)
    
    async def get_by_run_id(self, run_id: str) -> List[TestRunResult]:
        """根据运行ID查询所有结果"""
        return await self.get_by_filter(run_id=run_id)
```

- [ ] **Step 4: 编写PromptRepository**

```python
from typing import Optional, List
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import async_sessionmaker
from src.repository.base import BaseRepository
from src.models.prompt import PromptVersion, PromptABTest

class PromptVersionRepository(BaseRepository[PromptVersion]):
    def __init__(self, db_session_factory: async_sessionmaker):
        super().__init__(PromptVersion, db_session_factory)
    
    async def get_latest_version(self, prompt_key: str) -> Optional[PromptVersion]:
        """获取指定提示词的最新版本"""
        async with self.db_session_factory() as session:
            result = await session.execute(
                select(PromptVersion)
                .where(PromptVersion.prompt_key == prompt_key)
                .order_by(desc(PromptVersion.created_at))
                .limit(1)
            )
            return result.scalar_one_or_none()
    
    async def get_versions_by_key(self, prompt_key: str, skip: int = 0, limit: int = 20) -> List[PromptVersion]:
        """获取指定提示词的所有版本"""
        return await self.get_by_filter(skip=skip, limit=limit, order_by=desc(PromptVersion.created_at), prompt_key=prompt_key)

class PromptABTestRepository(BaseRepository[PromptABTest]):
    def __init__(self, db_session_factory: async_sessionmaker):
        super().__init__(PromptABTest, db_session_factory)
    
    async def get_active_test(self, prompt_key: str) -> Optional[PromptABTest]:
        """获取指定提示词的活跃A/B测试"""
        return await self.get_one_by_filter(prompt_key=prompt_key, is_active=True)
    
    async def get_all_active_tests(self) -> List[PromptABTest]:
        """获取所有活跃的A/B测试"""
        return await self.get_by_filter(is_active=True)
```

- [ ] **Step 5: 编写MonitorRepository**

```python
from typing import List
from sqlalchemy import select, desc, func
from sqlalchemy.ext.asyncio import async_sessionmaker
from src.repository.base import BaseRepository
from src.models.monitor import LLMCallLog, ABTestMetrics

class LLMCallLogRepository(BaseRepository[LLMCallLog]):
    def __init__(self, db_session_factory: async_sessionmaker):
        super().__init__(LLMCallLog, db_session_factory)
    
    async def get_logs_by_request_id(self, request_id: str) -> List[LLMCallLog]:
        """根据请求ID查询日志"""
        return await self.get_by_filter(request_id=request_id)
    
    async def get_recent_logs(self, limit: int = 100) -> List[LLMCallLog]:
        """获取最近的日志"""
        return await self.get_all(skip=0, limit=limit, order_by=desc(LLMCallLog.created_at))
    
    async def get_error_logs(self, skip: int = 0, limit: int = 50) -> List[LLMCallLog]:
        """获取失败日志
        
        注意: LLMCallStatus枚举值为success/failed/timeout，没有error
        """
        return await self.get_by_filter(skip=skip, limit=limit, order_by=desc(LLMCallLog.created_at), status="failed")
    
    async def get_logs_by_status(self, status: str, skip: int = 0, limit: int = 50) -> List[LLMCallLog]:
        """根据状态查询日志 (success/failed/timeout)"""
        return await self.get_by_filter(skip=skip, limit=limit, order_by=desc(LLMCallLog.created_at), status=status)

class ABTestMetricRepository(BaseRepository[ABTestMetrics]):
    def __init__(self, db_session_factory: async_sessionmaker):
        super().__init__(ABTestMetrics, db_session_factory)
    
    async def get_metrics_by_test(self, test_name: str) -> List[ABTestMetrics]:
        """获取指定测试的所有指标"""
        return await self.get_by_filter(test_name=test_name)
    
    async def get_metrics_by_variant(self, test_name: str, variant_name: str) -> List[ABTestMetrics]:
        """获取指定变体的指标"""
        return await self.get_by_filter(test_name=test_name, variant_name=variant_name)
```

- [ ] **Step 6: 编写__init__.py导出所有Repository**

```python
from .config_repository import ConfigVersionRepository, ConfigAuditLogRepository
from .document_repository import SourceDocumentRepository, DocumentRecordRepository
from .test_case_repository import (
    TestCaseRepository, TestCaseDraftRepository, 
    TestSetRepository, TestSetCaseRepository,
    TestRunRepository, TestRunResultRepository
)
from .prompt_repository import PromptVersionRepository, PromptABTestRepository
from .monitor_repository import LLMCallLogRepository, ABTestMetricRepository

__all__ = [
    # Config
    "ConfigVersionRepository",
    "ConfigAuditLogRepository",
    # Document
    "SourceDocumentRepository",
    "DocumentRecordRepository",
    # Test Case
    "TestCaseRepository",
    "TestCaseDraftRepository",
    "TestSetRepository",
    "TestSetCaseRepository",
    "TestRunRepository",
    "TestRunResultRepository",
    # Prompt
    "PromptVersionRepository",
    "PromptABTestRepository",
    # Monitor
    "LLMCallLogRepository",
    "ABTestMetricRepository",
]
```

---

### Task 3: 注册Repository到DI容器

**Files:**
- Modify: `src/core/di_container.py`

**重要修正**: 
- Repository接收`async_session_factory`而非`AsyncSession`
- 需要从`src.core.database`导入`async_session_factory`
- **实际代码结构**: 当前`di_container.py`直接在模块级别创建`injector = Injector([CoreModule()])`，无需新增`create_di_container()`函数，直接在现有初始化语句中添加`RepositoryModule()`

- [ ] **Step 1: 更新DI容器配置**

```python
from injector import Injector, Module, provider, singleton
from src.core.interfaces import (
    IIndexManager,
    ICacheService,
    IRetrievalService,
    IDocumentIngestionService
)
from src.core.database import async_session_factory
from src.repository import (
    ConfigVersionRepository, ConfigAuditLogRepository,
    SourceDocumentRepository, DocumentRecordRepository,
    TestCaseRepository, TestCaseDraftRepository, 
    TestSetRepository, TestSetCaseRepository, TestRunRepository, TestRunResultRepository,
    PromptVersionRepository, PromptABTestRepository,
    LLMCallLogRepository, ABTestMetricRepository
)

class CoreModule(Module):
    # ... 现有CoreModule代码保持不变 ...

class RepositoryModule(Module):
    """Repository依赖注入模块
    
    所有Repository共享同一个session_factory实例，
    每个方法内部独立创建session，保证并发安全。
    """
    
    @provider
    @singleton
    def provide_config_version_repository(self) -> ConfigVersionRepository:
        return ConfigVersionRepository(async_session_factory)
    
    @provider
    @singleton
    def provide_config_audit_log_repository(self) -> ConfigAuditLogRepository:
        return ConfigAuditLogRepository(async_session_factory)
    
    @provider
    @singleton
    def provide_source_document_repository(self) -> SourceDocumentRepository:
        return SourceDocumentRepository(async_session_factory)
    
    @provider
    @singleton
    def provide_document_record_repository(self) -> DocumentRecordRepository:
        return DocumentRecordRepository(async_session_factory)
    
    @provider
    @singleton
    def provide_test_case_repository(self) -> TestCaseRepository:
        return TestCaseRepository(async_session_factory)
    
    @provider
    @singleton
    def provide_test_case_draft_repository(self) -> TestCaseDraftRepository:
        return TestCaseDraftRepository(async_session_factory)
    
    @provider
    @singleton
    def provide_test_set_repository(self) -> TestSetRepository:
        return TestSetRepository(async_session_factory)
    
    @provider
    @singleton
    def provide_test_set_case_repository(self) -> TestSetCaseRepository:
        return TestSetCaseRepository(async_session_factory)
    
    @provider
    @singleton
    def provide_test_run_repository(self) -> TestRunRepository:
        return TestRunRepository(async_session_factory)
    
    @provider
    @singleton
    def provide_test_run_result_repository(self) -> TestRunResultRepository:
        return TestRunResultRepository(async_session_factory)
    
    @provider
    @singleton
    def provide_prompt_version_repository(self) -> PromptVersionRepository:
        return PromptVersionRepository(async_session_factory)
    
    @provider
    @singleton
    def provide_prompt_ab_test_repository(self) -> PromptABTestRepository:
        return PromptABTestRepository(async_session_factory)
    
    @provider
    @singleton
    def provide_llm_call_log_repository(self) -> LLMCallLogRepository:
        return LLMCallLogRepository(async_session_factory)
    
    @provider
    @singleton
    def provide_ab_test_metric_repository(self) -> ABTestMetricRepository:
        return ABTestMetricRepository(async_session_factory)

# 修改现有的injector创建语句，添加RepositoryModule
injector = Injector([CoreModule(), RepositoryModule()])
```

---

### Task 4: 分阶段迁移业务代码到Repository模式

**迁移策略**: 采用渐进式迁移，保持向后兼容，每个阶段可独立回滚

**优先级顺序**: 高内聚低耦合模块优先 → 核心业务模块

#### Task 4.1: Phase 1 - 迁移配置模块（低风险试点）

**目标**: 验证Repository模式可行性，建立迁移模板

**Files:**
- Modify: `src/config/core/manager.py`
- Note: 保留`src/config/core/repository.py`中的`MySQLConfigRepository`作为对照

- [ ] **Step 1: 在ConfigManager中注入ConfigVersionRepository**
- [ ] **Step 2: 逐步替换ConfigManager中的直接session操作为Repository调用**
- [ ] **Step 3: 保留原有MySQLConfigRepository代码作为fallback，验证功能一致性**
- [ ] **Step 4: 运行配置模块相关测试**
- [ ] **Step 5: 验证热重载、版本控制等核心功能正常**

**验收标准**: 配置读写功能完全正常，性能无下降

#### Task 4.2: Phase 2 - 迁移提示词和监控模块（中等风险）

**Files:**
- Modify: `src/core/prompt/manager.py`
- Modify: `src/service/monitoring_service.py`
- Modify: `src/core/ab_test_framework.py`

- [ ] **Step 1: 迁移PromptManager**
  - 注入`PromptVersionRepository`和`PromptABTestRepository`
  - 替换直接session操作
  - 验证Redis缓存逻辑正常
- [ ] **Step 2: 迁移MonitoringService**
  - 注入`LLMCallLogRepository`和`ABTestMetricRepository`
  - 替换直接session操作
- [ ] **Step 3: 迁移ABTestFramework**
  - 注入`ABTestMetricRepository`和`PromptABTestRepository`
  - 替换直接session操作
- [ ] **Step 4: 运行对应测试，验证功能**

#### Task 4.3: Phase 3 - 迁移测试用例管理模块（高风险，业务复杂）

**Files:**
- Modify: `src/service/rag_test_manager.py`
- Modify: `src/controller/rag_test_controller.py`

- [ ] **Step 1: 分析RagTestManager中的所有数据库操作**
- [ ] **Step 2: 注入所需Repository (TestCase, TestCaseDraft, TestSet, TestRun, TestRunResult等)**
- [ ] **Step 3: 处理同步方法中的异步session创建反模式**
  - 当前存在`loop = asyncio.new_event_loop()`的反模式
  - 改为纯异步方法或正确的事件循环处理
- [ ] **Step 4: 更新RagTestController**
- [ ] **Step 5: 运行RAG测试相关全量测试**

#### Task 4.4: Phase 4 - 迁移文档管理模块

**Files:**
- Modify: `src/service/document_ingestion_service.py`
- Modify: `src/service/document_manager.py`
- Modify: `src/controller/rag_controller.py` (文档相关部分)

- [ ] **Step 1: 迁移DocumentIngestionService**
  - 注入`SourceDocumentRepository`和`DocumentRecordRepository`
  - 替换文档导入流水线中的session操作
- [ ] **Step 2: 迁移DocumentManager**
- [ ] **Step 3: 更新RagController中文档管理相关接口**
- [ ] **Step 4: 运行文档导入相关测试**

#### Task 4.5: Phase 5 - 清理和收尾

**Files:**
- Modify: 其他仍有直接session操作的文件
- Delete: 已完全替换的旧Repository实现（如确认无引用）

- [ ] **Step 1: 扫描剩余直接session操作的文件**
- [ ] **Step 2: 逐个迁移**
- [ ] **Step 3: 删除废弃的旧代码**
- [ ] **Step 4: 代码审查和重构优化**

---

### Task 5: 验证与收尾

- [ ] **Step 1: 运行全量单元测试**
```bash
cd /Users/owen/project/ai/child-development-assessment-agent
pytest tests/ -v
```
Expected: All tests pass

- [ ] **Step 2: 运行全量集成测试**
```bash
cd /Users/owen/project/ai/child-development-assessment-agent
pytest tests/integration/ -v
```
Expected: All tests pass

- [ ] **Step 3: 性能基准测试**
- 对比迁移前后的关键接口响应时间
- 确认session创建/销毁开销在可接受范围
- 验证连接池配置合理

- [ ] **Step 4: 更新AGENTS.md文档，添加Repository层架构说明**
- [ ] **Step 5: 更新CLAUDE.md文档（如需要）**
- [ ] **Step 6: 提交代码到版本库**

---

## 三、架构优势

1. **并发安全**: Repository内部管理session生命周期，每个请求独立session，避免数据竞争
2. **代码复用**: 消除30个文件中的重复CRUD代码，统一数据操作实现
3. **可维护性**: 数据操作逻辑集中在Repository层，修改无需遍历所有业务文件
4. **一致性**: 所有数据操作经过统一入口，便于添加全局监控、权限校验、缓存逻辑
5. **可测试性**: Repository接口易于Mock，单元测试无需依赖真实数据库
6. **扩展性**: 后续切换数据库（如从MySQL切换到PostgreSQL）仅需修改Repository层实现，业务代码无需改动
7. **安全性**: 过滤查询时校验字段有效性，防止SQL注入风险

## 四、风险与缓解措施

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| Session创建开销 | 性能下降 | 使用连接池，benchmark验证 |
| 迁移引入bug | 功能异常 | 分阶段迁移，每阶段独立测试，保留fallback |
| DI容器配置错误 | 启动失败 | 单元测试验证DI配置 |
| 并发数据竞争 | 数据不一致 | Repository内部管理session，不共享session |

## 五、后续优化方向（不在本次范围）

1. **批量操作优化**: 添加`bulk_create`, `bulk_update`方法
2. **软删除支持**: BaseRepository增加软删除机制
3. **审计日志**: 自动记录create/update/delete操作
4. **缓存集成**: Repository层集成Redis缓存
5. **读写分离**: 查询走从库，写入走主库
