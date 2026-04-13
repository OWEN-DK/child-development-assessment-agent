from typing import TypeVar, Generic, List, Optional, Any, Dict
from sqlalchemy import select, func
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
            result = await session.execute(
                select(self.model).where(self.model.id == id)
            )
            return result.scalar_one_or_none()

    async def get_all(
        self,
        skip: int = 0,
        limit: int = 100,
        order_by: Optional[Any] = None,
    ) -> List[ModelType]:
        """查询所有记录，支持分页和排序"""
        async with self.db_session_factory() as session:
            query = select(self.model).offset(skip).limit(limit)
            if order_by is not None:
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
            result = await session.execute(
                select(self.model).where(self.model.id == obj_id)
            )
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
        from sqlalchemy import delete

        async with self.db_session_factory() as session:
            result = await session.execute(
                delete(self.model).where(self.model.id == id)
            )
            await session.commit()
            return result.rowcount > 0

    async def get_by_filter(
        self,
        skip: int = 0,
        limit: int = 100,
        order_by: Optional[Any] = None,
        **filters,
    ) -> List[ModelType]:
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
                    raise ValueError(
                        f"Invalid filter field '{field}' for model {self.model.__name__}"
                    )
                query = query.where(getattr(self.model, field) == value)

            if order_by is not None:
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
                    raise ValueError(
                        f"Invalid filter field '{field}' for model {self.model.__name__}"
                    )
                query = query.where(getattr(self.model, field) == value)

            result = await session.execute(query)
            return result.scalar_one_or_none()

    async def count_by_filter(self, **filters) -> int:
        """根据过滤条件统计记录数"""
        async with self.db_session_factory() as session:
            query = select(func.count()).select_from(self.model)
            for field, value in filters.items():
                if not hasattr(self.model, field):
                    raise ValueError(
                        f"Invalid filter field '{field}' for model {self.model.__name__}"
                    )
                query = query.where(getattr(self.model, field) == value)

            result = await session.execute(query)
            return result.scalar_one()
