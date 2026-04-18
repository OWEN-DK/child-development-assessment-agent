from pathlib import Path
from urllib.parse import quote

from pydantic import Field
from pydantic_settings import BaseSettings

BASE_DIR = Path(__file__).parent.parent.parent.parent.resolve()


class DatabaseSettings(BaseSettings):
    """MySQL 数据库配置"""

    db_host: str = Field(default="localhost", validation_alias="MYSQL_HOST")
    db_port: int = Field(default=3306, validation_alias="MYSQL_PORT")
    db_user: str = Field(default="root", validation_alias="MYSQL_USER")
    db_password: str = Field(default="", validation_alias="MYSQL_PASSWORD")
    db_name: str = Field(default="child_development", validation_alias="MYSQL_DATABASE")

    pool_size: int = Field(default=10, validation_alias="MYSQL_POOL_SIZE")
    max_overflow: int = Field(default=20, validation_alias="MYSQL_MAX_OVERFLOW")
    pool_timeout: int = Field(default=30, validation_alias="MYSQL_POOL_TIMEOUT")
    pool_recycle: int = Field(default=1800, validation_alias="MYSQL_POOL_RECYCLE")

    @property
    def async_url(self) -> str:
        """异步数据库连接 URL"""
        # 密码已经是编码后的，不需要二次编码
        return (
            f"mysql+aiomysql://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
            f"?charset=utf8mb4"
        )

    @property
    def sync_url(self) -> str:
        """同步数据库连接 URL（用于 Alembic 迁移）"""
        # 密码已经是编码后的，不需要二次编码
        return (
            f"mysql+pymysql://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
            f"?charset=utf8mb4"
        )

    model_config = {
        "env_file": str(BASE_DIR / ".env.dev"),
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


database_settings = DatabaseSettings()
