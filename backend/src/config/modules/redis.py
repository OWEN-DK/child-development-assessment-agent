from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings

BASE_DIR = Path(__file__).parent.parent.parent.parent.resolve()


class RedisSettings(BaseSettings):
    """Redis 缓存加速层配置"""

    redis_url: str = Field(
        default="redis://localhost:6379/0", validation_alias="REDIS_URL"
    )
    redis_password: str = Field(default="", validation_alias="REDIS_PASSWORD")

    redis_max_connections: int = Field(
        default=1000, validation_alias="REDIS_MAX_CONNECTIONS"
    )
    redis_max_idle: int = Field(default=10, validation_alias="REDIS_MAX_IDLE")
    redis_min_idle: int = Field(default=5, validation_alias="REDIS_MIN_IDLE")
    redis_socket_timeout: int = Field(
        default=15, validation_alias="REDIS_SOCKET_TIMEOUT"
    )
    redis_socket_connect_timeout: int = Field(
        default=10, validation_alias="REDIS_SOCKET_CONNECT_TIMEOUT"
    )

    cache_enabled: bool = Field(default=True, validation_alias="REDIS_CACHE_ENABLED")
    cache_default_ttl: int = Field(
        default=3600, validation_alias="REDIS_CACHE_DEFAULT_TTL"
    )
    cache_max_memory: str = Field(
        default="256mb", validation_alias="REDIS_CACHE_MAX_MEMORY"
    )

    lock_timeout: int = Field(default=30, validation_alias="REDIS_LOCK_TIMEOUT")
    lock_retry_interval: float = Field(
        default=0.1, validation_alias="REDIS_LOCK_RETRY_INTERVAL"
    )

    session_ttl: int = Field(default=86400, validation_alias="REDIS_SESSION_TTL")

    pubsub_enabled: bool = Field(default=True, validation_alias="REDIS_PUBSUB_ENABLED")
    pubsub_channels: list[str] = Field(
        default=["config:changed", "llm:call", "test:progress"],
        validation_alias="REDIS_PUBSUB_CHANNELS",
    )

    model_config = {
        "env_file": str(BASE_DIR / ".env"),
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


redis_settings = RedisSettings()
