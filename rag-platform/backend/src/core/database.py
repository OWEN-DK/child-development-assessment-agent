"""数据库引擎与 Session 工厂

从 .env 读取 DATABASE_URL，创建异步引擎和 Session 工厂。
"""
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.utils.logger import logger


def _create_engine():
    """创建异步数据库引擎"""
    from src.config import database_settings

    return create_async_engine(
        database_settings.database_url,
        echo=False,
        pool_size=database_settings.pool_size,
        max_overflow=database_settings.max_overflow,
        pool_timeout=database_settings.pool_timeout,
        pool_recycle=database_settings.pool_recycle,
        pool_pre_ping=True,
        pool_use_lifo=True,
    )


engine = _create_engine()

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# 兼容旧模块引用（monitoring_service 等使用 db_session_factory）
db_session_factory = async_session_factory


async def get_pool_status() -> dict:
    """获取连接池当前状态"""
    pool = engine.pool
    return {
        "pool_size": pool.size(),
        "checked_in": pool.checkedin(),
        "checked_out": pool.checkedout(),
        "overflow": pool.overflow(),
        "invalidated": pool.invalidated(),
    }
