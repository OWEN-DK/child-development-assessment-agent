"""RAG 核心配置：缓存、监控、评分配置"""
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings

BASE_DIR = Path(__file__).parent.parent.parent.parent.parent.resolve()


class RagCoreSettings(BaseSettings):
    # 缓存配置
    rag_cache_enabled: bool = Field(default=True, validation_alias="RAG_CACHE_ENABLED", description="是否启用缓存")
    rag_cache_max_size: int = Field(default=10000, validation_alias="RAG_CACHE_MAX_SIZE", description="缓存最大条目数")
    rag_cache_ttl_seconds: int = Field(default=3600, validation_alias="RAG_CACHE_TTL_SECONDS", description="缓存过期时间（秒）")
    rag_cache_disk_enabled: bool = Field(
        default=True, validation_alias="RAG_CACHE_DISK_ENABLED", description="是否启用磁盘缓存持久化"
    )
    rag_cache_disk_dir: str = Field(
        default="", validation_alias="RAG_CACHE_DISK_DIR", description="磁盘缓存目录路径"
    )
    rag_cache_disk_persist_interval: int = Field(
        default=300, validation_alias="RAG_CACHE_DISK_PERSIST_INTERVAL", description="磁盘缓存持久化间隔（秒）"
    )

    # 监控配置
    rag_monitoring_log_level: str = Field(
        default="INFO", validation_alias="RAG_MONITORING_LOG_LEVEL", description="监控日志级别"
    )
    rag_monitoring_metrics_interval: int = Field(
        default=60, validation_alias="RAG_MONITORING_METRICS_INTERVAL", description="指标采集间隔（秒）"
    )

    class Config:
        env_file = str(BASE_DIR / ".env")
        env_file_encoding = "utf-8"
