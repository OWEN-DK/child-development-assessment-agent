"""应用基础配置"""
from pydantic import Field
from pydantic_settings import BaseSettings


class AppSettings(BaseSettings):
    app_host: str = Field("0.0.0.0", validation_alias="APP_HOST", description="服务绑定IP地址")
    app_port: int = Field(51002, validation_alias="APP_PORT", description="服务监听端口")
    app_reload: bool = Field(True, validation_alias="APP_RELOAD", description="是否启用代码热重载")
    app_workers: int = Field(1, validation_alias="APP_WORKERS", description="Uvicorn worker 数量")
    debug: bool = Field(True, validation_alias="DEBUG", description="是否启用调试模式")
    environment: str = Field("development", validation_alias="ENVIRONMENT", description="运行环境")
    rag_monitoring_enabled: bool = Field(True, validation_alias="RAG_MONITORING_ENABLED", description="是否启用 RAG 监控")
