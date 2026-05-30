"""Neo4j Driver 单例管理。

放置位置: backend/src/core/knowledge_qa/neo4j/driver.py
"""

import logging

from neo4j import GraphDatabase, ServiceUnavailable, SessionExpired

logger = logging.getLogger(__name__)

_driver = None


def get_neo4j_driver(config_manager=None):
    """获取 Neo4j driver 单例。NEO4J_ENABLED=False 时返回 None。

    Args:
        config_manager: 配置管理器实例。实际部署时通过 DI 注入。
    """
    global _driver

    if config_manager is None:
        from config.core.manager import config_manager as _cm
        config_manager = _cm

    if not config_manager.get("neo4j.enabled", False):
        return None

    if _driver is None:
        uri = config_manager.get("neo4j.uri", "bolt://localhost:7687")
        user = config_manager.get("neo4j.user", "neo4j")
        password = config_manager.get("neo4j.password", "devpass123")

        _driver = GraphDatabase.driver(
            uri,
            auth=(user, password),
            max_connection_lifetime=config_manager.get("neo4j.max_connection_lifetime", 3600),
            max_connection_pool_size=config_manager.get("neo4j.max_connection_pool_size", 50),
            connection_acquisition_timeout=config_manager.get("neo4j.connection_acquisition_timeout", 30),
        )
        logger.info("Neo4j driver initialized: %s", uri)

    return _driver


def close_neo4j_driver():
    """关闭 Neo4j driver（应用关闭时调用）。"""
    global _driver
    if _driver:
        _driver.close()
        _driver = None
        logger.info("Neo4j driver closed")


def neo4j_available() -> bool:
    """检查 Neo4j 是否可用。"""
    from config.core.manager import config_manager

    if not config_manager.get("neo4j.enabled", False):
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
