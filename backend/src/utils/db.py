"""数据库工具模块

统一管理数据库 Session 生命周期，消除重复代码。
"""

from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, Callable

from src.core.database import async_session_factory


@asynccontextmanager
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """统一数据库会话获取

    使用方式：
        async with get_db_session() as session:
            result = await session.execute(select(User))

    自动处理 commit/rollback，业务代码无需手动调用。
    """
    from sqlalchemy.ext.asyncio import AsyncSession

    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def execute_with_session(
    func: Callable, *args: Any, **kwargs: Any
) -> Any:
    """自动管理 session 生命周期的执行器

    使用方式：
        result = await execute_with_session(my_service_method, arg1, arg2)
    """
    async with async_session_factory() as session:
        try:
            result = await func(session, *args, **kwargs)
            await session.commit()
            return result
        except Exception:
            await session.rollback()
            raise


async def execute_readonly(
    func: Callable, *args: Any, **kwargs: Any
) -> Any:
    """只读查询执行器（不提交）

    使用方式：
        result = await execute_readonly(my_query_method, arg1)
    """
    async with async_session_factory() as session:
        return await func(session, *args, **kwargs)
