from pydantic import Field
from pydantic_settings import BaseSettings
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent.parent.parent.resolve()


class Neo4jSettings(BaseSettings):
    """Neo4j 图数据库配置"""

    neo4j_enabled: bool = Field(default=False, validation_alias="NEO4J_ENABLED")
    neo4j_uri: str = Field(default="bolt://localhost:7687", validation_alias="NEO4J_URI")
    neo4j_user: str = Field(default="neo4j", validation_alias="NEO4J_USER")
    neo4j_password: str = Field(default="devpass123", validation_alias="NEO4J_PASSWORD")
    neo4j_query_timeout: int = Field(default=30, validation_alias="NEO4J_QUERY_TIMEOUT")
    neo4j_max_pool_size: int = Field(default=50, validation_alias="NEO4J_MAX_POOL_SIZE")
    neo4j_rollout_percentage: int = Field(default=0, validation_alias="NEO4J_ROLLOUT_PERCENTAGE")

    model_config = {
        "env_file": str(BASE_DIR / ".env.dev"),
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


neo4j_settings = Neo4jSettings()
