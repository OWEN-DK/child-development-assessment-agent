from pydantic import Field
from pydantic_settings import BaseSettings

class LogSettings(BaseSettings):
    log_level: str = Field("INFO", validation_alias="LOG_LEVEL", description="日志输出级别")
    log_file: str = Field("./logs/app.log", validation_alias="LOG_FILE", description="日志文件存储路径")
