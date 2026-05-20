"""通用 CRUD Repository 基类

设计要点：
- 接收 session_factory 而非单个 session，避免并发数据竞争
- 每个方法内部管理 session 生命周期
- 自动注入 tenant_id 过滤（行级隔离）
- 超管专用 _get_admin_session() 不做过滤
"""
from typing import Any, Dict, Generic, List, Optional, TypeVar

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from src.core.auth.exceptions import MissingTenantContextError
from src.utils.exceptions import InvalidParamsException, ResourceNotFoundException

ModelType = TypeVar("ModelType", bound=DeclarativeBase)


class BaseRepository(Generic[ModelType]):
    """通用 CRUD Repository 基类"""

    def __init__(self, model: type[ModelType], db_session_factory: async_sessionmaker):
        self.model = model
        self.db_session_factory = db_session_factory

    # ── Session 管理 ──────────────────────────────────

    def _get_session(self, tenant_id: str | None):
        """获取带 tenant_id 过滤的 session

        Args:
            tenant_id: 租户 ID（必须传入，超管请用 _get_admin_session）

        Raises:
            MissingTenantContextError: tenant_id 为 None
        """
        if tenant_id is None:
            raise MissingTenantContextError(
                message="数据访问必须传入 tenant_id，超管请用 _get_admin_session()"
            )
        return self.db_session_factory()

    def _get_admin_session(self):
        """获取超管专用 session（不做 tenant_id 过滤）"""
        return self.db_session_factory()

    def _add_tenant_filter(self, stmt, tenant_id: str | None):
        """自动注入 WHERE tenant_id 条件

        Args:
            stmt: SQLAlchemy select 语句
            tenant_id: 租户 ID（None 时跳过过滤，用于超管场景）
        """
        if tenant_id is not None and hasattr(self.model, "tenant_id"):
            stmt = stmt.where(self.model.tenant_id == tenant_id)
        return stmt

    # ── CRUD 操作 ─────────────────────────────────────

    async def get_by_id(self, id: Any, tenant_id: str | None = None) -> Optional[ModelType]:
        """根据 ID 查询单个记录（自动注入 tenant_id 过滤）"""
        async with self.db_session_factory() as session:
            stmt = select(self.model).where(self.model.id == id)
            stmt = self._add_tenant_filter(stmt, tenant_id)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def get_all(
        self,
        tenant_id: str | None = None,
        skip: int = 0,
        limit: int = 100,
        order_by: Optional[Any] = None,
    ) -> List[ModelType]:
        """查询所有记录（自动注入 tenant_id 过滤）"""
        async with self.db_session_factory() as session:
            stmt = select(self.model)
            stmt = self._add_tenant_filter(stmt, tenant_id)
            if order_by is not None:
                stmt = stmt.order_by(order_by)
            stmt = stmt.offset(skip).limit(limit)
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def count(self, tenant_id: str | None = None) -> int:
        """统计记录数"""
        async with self.db_session_factory() as session:
            stmt = select(func.count()).select_from(self.model)
            stmt = self._add_tenant_filter(stmt, tenant_id)
            result = await session.execute(stmt)
            return result.scalar() or 0

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

    async def update(self, obj_id: Any, obj_data: Dict[str, Any], tenant_id: str | None = None) -> ModelType:
        """更新现有记录

        Args:
            obj_id: 记录 ID
            obj_data: 要更新的字段字典
            tenant_id: 租户 ID（自动过滤）
        """
        async with self.db_session_factory() as session:
            stmt = select(self.model).where(self.model.id == obj_id)
            stmt = self._add_tenant_filter(stmt, tenant_id)
            result = await session.execute(stmt)
            db_obj = result.scalar_one_or_none()
            if db_obj is None:
                raise ResourceNotFoundException(message=f"{self.model.__name__} not found: id={obj_id}")
            for field, value in obj_data.items():
                setattr(db_obj, field, value)
            await session.commit()
            await session.refresh(db_obj)
            return db_obj

    async def delete(self, id: Any, tenant_id: str | None = None) -> bool:
        """根据 ID 删除记录"""
        from sqlalchemy import delete

        async with self.db_session_factory() as session:
            stmt = delete(self.model).where(self.model.id == id)
            if tenant_id is not None and hasattr(self.model, "tenant_id"):
                stmt = stmt.where(self.model.tenant_id == tenant_id)
            result = await session.execute(stmt)
            await session.commit()
            return result.rowcount > 0

    async def get_by_filter(
        self,
        tenant_id: str | None = None,
        skip: int = 0,
        limit: int = 100,
        order_by: Optional[Any] = None,
        **filters,
    ) -> List[ModelType]:
        """根据过滤条件查询多条记录（自动注入 tenant_id 过滤）"""
        async with self.db_session_factory() as session:
            stmt = select(self.model)
            stmt = self._add_tenant_filter(stmt, tenant_id)
            for field, value in filters.items():
                if not hasattr(self.model, field):
                    raise InvalidParamsException(message=f"Invalid filter field '{field}' for model {self.model.__name__}")
                stmt = stmt.where(getattr(self.model, field) == value)
            if order_by is not None:
                stmt = stmt.order_by(order_by)
            stmt = stmt.offset(skip).limit(limit)
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def get_one_by_filter(self, tenant_id: str | None = None, **filters) -> Optional[ModelType]:
        """根据过滤条件查询单个记录"""
        async with self.db_session_factory() as session:
            stmt = select(self.model)
            stmt = self._add_tenant_filter(stmt, tenant_id)
            for field, value in filters.items():
                if not hasattr(self.model, field):
                    raise InvalidParamsException(message=f"Invalid filter field '{field}' for model {self.model.__name__}")
                stmt = stmt.where(getattr(self.model, field) == value)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()
