"""RAG 核心配置：缓存、监控、通用开关"""

from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings

BASE_DIR = Path(__file__).parent.parent.parent.parent.resolve()


class RagCoreSettings(BaseSettings):
    """RAG 核心配置"""

    # 通用开关
    rag_enabled: bool = Field(
        default=True, validation_alias="RAG_ENABLED", description="是否启用 RAG 系统"
    )
    rag_default_top_k: int = Field(
        default=10, validation_alias="RAG_DEFAULT_TOP_K", description="默认返回结果数"
    )
    rag_search_mode: str = Field(
        default="hybrid",
        validation_alias="RAG_SEARCH_MODE",
        description="搜索模式：hybrid/vector/bm25",
    )

    # 缓存配置
    rag_cache_enabled: bool = Field(
        default=True, validation_alias="RAG_CACHE_ENABLED", description="是否启用缓存"
    )
    rag_cache_max_size: int = Field(
        default=1000,
        validation_alias="RAG_CACHE_MAX_SIZE",
        description="缓存最大条目数",
    )
    rag_cache_ttl_seconds: int = Field(
        default=3600,
        validation_alias="RAG_CACHE_TTL_SECONDS",
        description="缓存过期时间（秒）",
    )
    rag_cache_disk_enabled: bool = Field(
        default=True,
        validation_alias="RAG_CACHE_DISK_ENABLED",
        description="是否启用磁盘缓存持久化",
    )
    rag_cache_disk_dir: str = Field(
        default="",
        validation_alias="RAG_CACHE_DISK_DIR",
        description="磁盘缓存目录路径，为空时使用 app_data/cache",
    )
    rag_cache_disk_persist_interval: int = Field(
        default=300,
        validation_alias="RAG_CACHE_DISK_PERSIST_INTERVAL",
        description="磁盘缓存持久化间隔（秒）",
    )

    # 监控配置
    rag_monitoring_enabled: bool = Field(
        default=True,
        validation_alias="RAG_MONITORING_ENABLED",
        description="是否启用监控",
    )
    rag_monitoring_log_level: str = Field(
        default="INFO",
        validation_alias="RAG_MONITORING_LOG_LEVEL",
        description="监控日志级别",
    )
    rag_monitoring_metrics_interval: int = Field(
        default=60,
        validation_alias="RAG_MONITORING_METRICS_INTERVAL",
        description="指标采集间隔（秒）",
    )

    class Config:
        env_file = str(BASE_DIR / ".env.dev")
        env_file_encoding = "utf-8"
