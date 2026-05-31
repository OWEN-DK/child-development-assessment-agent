"""Neo4j Driver 单例管理。"""

import logging

from neo4j import GraphDatabase
from neo4j import AsyncGraphDatabase
from neo4j.exceptions import ServiceUnavailable, SessionExpired

logger = logging.getLogger(__name__)

_driver = None
_async_driver = None


def _get_neo4j_settings():
    """获取 Neo4j 配置，优先使用 Pydantic Settings。"""
    from src.config.modules.neo4j import neo4j_settings
    return neo4j_settings


def get_neo4j_driver():
    """获取 Neo4j driver 单例。NEO4J_ENABLED=False 时返回 None。"""
    global _driver

    settings = _get_neo4j_settings()

    if not settings.neo4j_enabled:
        return None

    if _driver is None:
        _driver = GraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
            max_connection_pool_size=settings.neo4j_max_pool_size,
            connection_acquisition_timeout=30,
        )
        logger.info("Neo4j driver initialized: %s", settings.neo4j_uri)

    return _driver


def close_neo4j_driver():
    """关闭 Neo4j driver（应用关闭时调用）。"""
    global _driver
    if _driver:
        _driver.close()
        _driver = None
        logger.info("Neo4j driver closed")


def get_async_neo4j_driver():
    """获取 Neo4j async driver 单例。NEO4J_ENABLED=False 时返回 None。"""
    global _async_driver

    settings = _get_neo4j_settings()

    if not settings.neo4j_enabled:
        return None

    if _async_driver is None:
        _async_driver = AsyncGraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
            max_connection_pool_size=settings.neo4j_max_pool_size,
            connection_acquisition_timeout=30,
        )
        logger.info("Neo4j async driver initialized: %s", settings.neo4j_uri)

    return _async_driver


async def close_async_neo4j_driver():
    """关闭 Neo4j async driver（应用关闭时调用）。"""
    global _async_driver
    if _async_driver:
        await _async_driver.close()
        _async_driver = None
        logger.info("Neo4j async driver closed")


def neo4j_available() -> bool:
    """检查 Neo4j 是否可用。"""
    settings = _get_neo4j_settings()

    if not settings.neo4j_enabled:
        return False

    driver = get_neo4j_driver()
    if driver is None:
        return False

    try:
        with driver.session() as session:
            session.run("RETURN 1")
        return True
    except (ServiceUnavailable, SessionExpired, OSError):
        return False
