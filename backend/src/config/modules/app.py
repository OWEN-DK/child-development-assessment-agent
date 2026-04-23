from pydantic import Field
from pydantic_settings import BaseSettings
import os


class AppSettings(BaseSettings):
    app_name: str = Field("Child Development Assessment Agent", description="应用名称")
    app_version: str = Field("0.1.0", description="应用版本号")
    debug: bool = Field(True, description="是否启用调试模式")
    app_host: str = Field("127.0.0.1", description="服务绑定IP地址")
    app_port: int = Field(8000, description="服务监听端口")
    app_reload: bool = Field(False, description="是否启用代码热重载")
    app_workers: int = Field(
        default_factory=lambda: min(4, os.cpu_count() or 2),
        description="Uvicorn worker 数量（多实例部署时建议 2-4）",
    )
    multi_instance_deployment: bool = Field(False, description="是否多实例部署")
