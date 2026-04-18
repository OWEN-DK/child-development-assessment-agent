"""追踪系统配置模块"""

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class TracingConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_nested_delimiter="__",
        extra="ignore",
    )

    enabled: bool = Field(default=True, description="是否启用追踪")
    sample_rate: float = Field(default=1.0, ge=0.0, le=1.0, description="采样率")
    error_sample_rate: float = Field(
        default=1.0, ge=0.0, le=1.0, description="错误采样率"
    )
    truncate_length: int = Field(default=8000, gt=0, description="截断长度")
    full_content_enabled: bool = Field(default=False, description="是否存储完整内容")
    full_content_dir: str = Field(
        default="storage/traces", description="完整内容存储目录"
    )
    ttl_days: int = Field(default=30, gt=0, description="数据保留天数")
    cleanup_batch_size: int = Field(default=1000, gt=0, description="清理批次大小")
