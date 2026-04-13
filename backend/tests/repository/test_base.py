import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from src.repository.base import BaseRepository

pytestmark = pytest.mark.asyncio


class Base(DeclarativeBase):
    pass


class SampleModel(Base):
    __tablename__ = "sample_models"
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
    repo = BaseRepository[SampleModel](SampleModel, db_session_factory)

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
    repo = BaseRepository[SampleModel](SampleModel, db_session_factory)

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
    repo = BaseRepository[SampleModel](SampleModel, db_session_factory)

    # 创建无序记录 (使用唯一ID)
    for idx, i in enumerate([3, 1, 4, 1, 5]):
        await repo.create({"id": f"order_{idx}", "name": "order_test", "value": i})

    # 测试升序
    from sqlalchemy import asc

    asc_results = await repo.get_all(order_by=asc(SampleModel.value))
    assert [r.value for r in asc_results] == [1, 1, 3, 4, 5]

    # 测试降序
    from sqlalchemy import desc

    desc_results = await repo.get_all(order_by=desc(SampleModel.value))
    assert [r.value for r in desc_results] == [5, 4, 3, 1, 1]


async def test_base_repository_get_one_by_filter(db_session_factory):
    repo = BaseRepository[SampleModel](SampleModel, db_session_factory)

    # 创建记录
    await repo.create({"id": "unique_1", "name": "unique", "value": 42})

    # 测试单个查询
    result = await repo.get_one_by_filter(name="unique")
    assert result is not None
    assert result.value == 42

    # 测试不存在的记录
    result = await repo.get_one_by_filter(name="nonexistent")
    assert result is None


async def test_base_repository_delete_nonexistent(db_session_factory):
    repo = BaseRepository[SampleModel](SampleModel, db_session_factory)

    # 测试删除不存在的记录
    result = await repo.delete("nonexistent")
    assert result is False
