from pydantic import Field
from pydantic_settings import BaseSettings


class PageIndexSettings(BaseSettings):
    pageindex_enabled: bool = Field(
        default=False,
        validation_alias="PAGEINDEX_ENABLED",
        description="是否启用PageIndex全网检索功能"
    )
    pageindex_base_url: str = Field(
        default="https://api.pageindex.ai",
        validation_alias="PAGEINDEX_BASE_URL",
        description="PageIndex服务API地址"
    )
    pageindex_api_key: str = Field(
        default="",
        validation_alias="PAGEINDEX_API_KEY",
        description="PageIndex服务API密钥"
    )
    pageindex_max_concurrency: int = Field(
        default=5,
        validation_alias="PAGEINDEX_MAX_CONCURRENCY",
        description="PageIndex最大并发请求数"
    )
    pageindex_max_tree_depth: int = Field(
        default=3,
        validation_alias="PAGEINDEX_MAX_TREE_DEPTH",
        description="PageIndex检索结果最大树深度"
    )
    pageindex_timeout_seconds: int = Field(
        default=10,
        validation_alias="PAGEINDEX_TIMEOUT_SECONDS",
        description="PageIndex请求超时时间（秒）"
    )
    pageindex_circuit_breaker_failure_threshold: int = Field(
        default=5,
        validation_alias="PAGEINDEX_CIRCUIT_BREAKER_FAILURE_THRESHOLD",
        description="PageIndex熔断失败次数阈值"
    )
    pageindex_circuit_breaker_reset_timeout: int = Field(
        default=60,
        validation_alias="PAGEINDEX_CIRCUIT_BREAKER_RESET_TIMEOUT",
        description="PageIndex熔断后自动重置时间（秒）"
    )
    pageindex_max_retries: int = Field(
        default=3,
        validation_alias="PAGEINDEX_MAX_RETRIES",
        description="PageIndex请求最大重试次数"
    )
    pageindex_retry_base_delay: float = Field(
        default=0.5,
        validation_alias="PAGEINDEX_RETRY_BASE_DELAY",
        description="PageIndex重试基础延迟（秒）"
    )
    pageindex_retry_max_delay: float = Field(
        default=10.0,
        validation_alias="PAGEINDEX_RETRY_MAX_DELAY",
        description="PageIndex重试最大延迟（秒）"
    )
    pageindex_fallback_to_hybrid: bool = Field(
        default=True,
        validation_alias="PAGEINDEX_FALLBACK_TO_HYBRID",
        description="PageIndex失败时是否降级到本地混合检索"
    )
