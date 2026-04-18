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

    # 评分配置
    rag_scoring_keyword_bonus_multiplier: float = Field(
        default=0.2,
        validation_alias="RAG_SCORING_KEYWORD_BONUS_MULTIPLIER",
        description="关键词匹配加成系数",
    )
    rag_scoring_max_expected_score: float = Field(
        default=0.65,
        validation_alias="RAG_SCORING_MAX_EXPECTED_SCORE",
        description="最大预期内部分数",
    )
    rag_scoring_base_display_score: float = Field(
        default=0.60,
        validation_alias="RAG_SCORING_BASE_DISPLAY_SCORE",
        description="基础展示分数",
    )
    rag_scoring_max_display_score: float = Field(
        default=0.98,
        validation_alias="RAG_SCORING_MAX_DISPLAY_SCORE",
        description="最大展示分数",
    )

    # 年龄过滤配置
    rag_age_filter_stage_boundaries: dict = Field(
        default_factory=lambda: {
            "infant": 1,
            "toddler": 3,
            "preschool": 6,
        },
        validation_alias="RAG_AGE_FILTER_STAGE_BOUNDARIES",
        description="儿童发展阶段年龄边界",
    )
    rag_age_fit_base_score: float = Field(
        default=0.5,
        validation_alias="RAG_AGE_FIT_BASE_SCORE",
        description="年龄适配度基础分数",
    )
    rag_age_fit_decay_factor: float = Field(
        default=0.1,
        validation_alias="RAG_AGE_FIT_DECAY_FACTOR",
        description="年龄适配度衰减系数",
    )
    rag_age_fit_threshold_high: float = Field(
        default=0.7,
        validation_alias="RAG_AGE_FIT_THRESHOLD_HIGH",
        description="年龄适配度高阈值（±1 岁）",
    )
    rag_age_fit_threshold_low: float = Field(
        default=0.3,
        validation_alias="RAG_AGE_FIT_THRESHOLD_LOW",
        description="年龄适配度低阈值（超出范围）",
    )
    rag_age_fit_default_score: float = Field(
        default=0.5,
        validation_alias="RAG_AGE_FIT_DEFAULT_SCORE",
        description="年龄适配度默认分数（异常时）",
    )
    rag_age_milestone_match_range_start: int = Field(
        default=6,
        validation_alias="RAG_AGE_MILESTONE_MATCH_RANGE_START",
        description="里程碑匹配年龄范围起始",
    )
    rag_age_milestone_match_range_end: int = Field(
        default=2,
        validation_alias="RAG_AGE_MILESTONE_MATCH_RANGE_END",
        description="里程碑匹配年龄范围结束（不包含）",
    )
    rag_age_default_range_min: int = Field(
        default=3,
        validation_alias="RAG_AGE_DEFAULT_RANGE_MIN",
        description="默认年龄范围最小值",
    )
    rag_age_default_range_max: int = Field(
        default=6,
        validation_alias="RAG_AGE_DEFAULT_RANGE_MAX",
        description="默认年龄范围最大值",
    )
    rag_unsuitable_content_threshold: float = Field(
        default=0.5,
        validation_alias="RAG_UNSUITABLE_CONTENT_THRESHOLD",
        description="不适宜内容过滤阈值",
    )

    class Config:
        env_file = str(BASE_DIR / ".env.dev")
        env_file_encoding = "utf-8"
