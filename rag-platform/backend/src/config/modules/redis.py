"""Redis 缓存配置"""
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings

BASE_DIR = Path(__file__).parent.parent.parent.parent.resolve()


class RedisSettings(BaseSettings):
    redis_url: str = Field(
        default="redis://:ragredis@localhost:6379/0",
        validation_alias="REDIS_URL",
        description="Redis 连接 URL",
    )
    redis_max_connections: int = Field(default=100, validation_alias="REDIS_MAX_CONNECTIONS", description="最大连接数")
    redis_socket_timeout: int = Field(default=5, validation_alias="REDIS_SOCKET_TIMEOUT", description="Socket 超时（秒）")
    redis_socket_connect_timeout: int = Field(
        default=5, validation_alias="REDIS_SOCKET_CONNECT_TIMEOUT", description="连接超时（秒）"
    )
    cache_enabled: bool = Field(default=True, validation_alias="REDIS_CACHE_ENABLED", description="是否启用 Redis 缓存")
    cache_default_ttl: int = Field(default=3600, validation_alias="REDIS_CACHE_DEFAULT_TTL", description="缓存默认 TTL（秒）")
    pubsub_enabled: bool = Field(default=True, validation_alias="REDIS_PUBSUB_ENABLED", description="是否启用 Pub/Sub")

    model_config = {
        "env_file": str(BASE_DIR / ".env"),
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


redis_settings = RedisSettings()
