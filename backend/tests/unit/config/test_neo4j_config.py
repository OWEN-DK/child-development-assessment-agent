"""Neo4j 配置模块测试。"""

import pytest


class TestNeo4jSettings:
    """Neo4jSettings Pydantic 模型测试。"""

    def test_default_values(self):
        from src.config.modules.neo4j import Neo4jSettings

        settings = Neo4jSettings()
        assert settings.neo4j_enabled is False
        assert settings.neo4j_uri == "bolt://localhost:7687"
        assert settings.neo4j_user == "neo4j"
        assert settings.neo4j_password == "devpass123"
        assert settings.neo4j_query_timeout == 30
        assert settings.neo4j_max_pool_size == 50
        assert settings.neo4j_rollout_percentage == 0

    def test_singleton_instance(self):
        from src.config.modules.neo4j import neo4j_settings

        assert neo4j_settings is not None
        assert hasattr(neo4j_settings, "neo4j_enabled")

    def test_settings_exported_from_modules(self):
        from src.config.modules import Neo4jSettings, neo4j_settings

        assert Neo4jSettings is not None
        assert neo4j_settings is not None
