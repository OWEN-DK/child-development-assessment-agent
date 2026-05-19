"""MySQL 数据库配置"""
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings

BASE_DIR = Path(__file__).parent.parent.parent.parent.resolve()


class DatabaseSettings(BaseSettings):
    database_url: str = Field(
        default="mysql+aiomysql://raguser:ragpass@localhost:3306/rag_platform",
        validation_alias="DATABASE_URL",
        description="异步数据库连接 URL",
    )
    pool_size: int = Field(default=10, validation_alias="MYSQL_POOL_SIZE", description="连接池大小")
    max_overflow: int = Field(default=20, validation_alias="MYSQL_MAX_OVERFLOW", description="最大溢出连接数")
    pool_timeout: int = Field(default=30, validation_alias="MYSQL_POOL_TIMEOUT", description="连接池超时（秒）")
    pool_recycle: int = Field(default=1800, validation_alias="MYSQL_POOL_RECYCLE", description="连接回收时间（秒）")

    model_config = {
        "env_file": str(BASE_DIR / ".env"),
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


database_settings = DatabaseSettings()
