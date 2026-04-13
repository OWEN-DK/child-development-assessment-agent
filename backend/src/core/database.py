import time
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import event
from src.config import database_settings, settings
from src.utils.logger import logger

engine = create_async_engine(
    database_settings.async_url,
    echo=False,  # 关闭自带的 echo，改为通过 logger 拦截
    pool_size=database_settings.pool_size,
    max_overflow=database_settings.max_overflow,
    pool_timeout=database_settings.pool_timeout,
    pool_recycle=database_settings.pool_recycle,
    pool_pre_ping=True,
    pool_use_lifo=True,
    echo_pool=False,  # 关闭自带的 echo_pool
)

# 手动设置 SQLAlchemy 日志级别，让 InterceptHandler 接管
import logging
if settings.debug:
    logging.getLogger("sqlalchemy.engine").setLevel(logging.INFO)
    logging.getLogger("sqlalchemy.pool").setLevel(logging.DEBUG)
else:
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.pool").setLevel(logging.WARNING)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """SQLAlchemy 声明式基类"""

    pass


SLOW_QUERY_THRESHOLD_MS = 100


@event.listens_for(engine.sync_engine, "before_cursor_execute")
def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    conn.info.setdefault("query_start_time", []).append(time.time())


@event.listens_for(engine.sync_engine, "after_cursor_execute")
def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    total = time.time() - conn.info["query_start_time"].pop(-1)
    duration_ms = total * 1000

    if duration_ms > SLOW_QUERY_THRESHOLD_MS:
        logger.warning(
            f"慢查询检测: {duration_ms:.2f}ms\nSQL: {statement}\n参数: {parameters}"
        )


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


async def check_pool_health() -> dict:
    """检查连接池健康状态"""
    status = await get_pool_status()
    alerts = []

    pool_size = status["pool_size"]
    if pool_size > 0:
        usage_rate = status["checked_out"] / pool_size
        if usage_rate > 0.8:
            alerts.append(f"连接池使用率过高: {usage_rate:.0%}")

    if status["overflow"] > 16:
        alerts.append(f"溢出连接过多: {status['overflow']}")

    return {
        "status": "healthy" if not alerts else "warning",
        "alerts": alerts,
        **status,
    }


db_session_factory = async_session_factory
