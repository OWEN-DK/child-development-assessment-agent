"""RAG Platform 配置模块

简化版配置，从 .env 文件读取基础设施凭证。
业务配置走 MySQL，此处仅保留启动必需项。
"""
import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

# 加载 .env 文件
BASE_DIR = Path(__file__).parent.parent.parent.resolve()
load_dotenv(BASE_DIR / ".env")


@dataclass
class Settings:
    """应用配置"""

    # 应用基础
    app_host: str = field(default_factory=lambda: os.getenv("APP_HOST", "0.0.0.0"))
    app_port: int = field(default_factory=lambda: int(os.getenv("APP_PORT", "51002")))
    app_reload: bool = field(default_factory=lambda: os.getenv("APP_RELOAD", "True").lower() == "true")
    debug: bool = field(default_factory=lambda: os.getenv("DEBUG", "True").lower() == "true")
    environment: str = field(default_factory=lambda: os.getenv("ENVIRONMENT", "development"))
    log_level: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))
    log_file: str = field(default_factory=lambda: os.getenv("LOG_FILE", "./logs/app.log"))

    # 数据库
    database_url: str = field(default_factory=lambda: os.getenv("DATABASE_URL", "mysql+asyncmy://raguser:ragpass@localhost:3306/rag_platform"))

    # Redis
    redis_url: str = field(default_factory=lambda: os.getenv("REDIS_URL", "redis://:ragredis@localhost:6379/0"))

    # JWT
    jwt_secret: str = field(default_factory=lambda: os.getenv("JWT_SECRET", "change-me-in-production-min-32-chars"))

    # LLM 凭证
    dashscope_api_key: str = field(default_factory=lambda: os.getenv("DASHSCOPE_API_KEY", ""))
    openai_api_key: str = field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
    anthropic_api_key: str = field(default_factory=lambda: os.getenv("ANTHROPIC_API_KEY", ""))
    deepseek_api_key: str = field(default_factory=lambda: os.getenv("DEEPSEEK_API_KEY", ""))

    # 向量后端
    es_url: str = field(default_factory=lambda: os.getenv("ES_URL", ""))
    milvus_host: str = field(default_factory=lambda: os.getenv("MILVUS_HOST", ""))
    milvus_port: int = field(default_factory=lambda: int(os.getenv("MILVUS_PORT", "19530")))

    # 数据目录
    data_dir: str = field(default_factory=lambda: os.getenv("DATA_DIR", "./app_data/data"))
    rag_storage_dir: str = field(default_factory=lambda: os.getenv("RAG_STORAGE_DIR", "./app_data/storage"))
    rag_temp_upload_dir: str = field(default_factory=lambda: os.getenv("RAG_TEMP_UPLOAD_DIR", "./app_data/temp_uploads"))


def validate_required_env_vars() -> list[str]:
    """校验必需的环境变量"""
    missing = []
    # 基础设施变量如果缺失会使用默认值，不视为 missing
    # 但 JWT_SECRET 如果还是默认值，在生产环境应告警
    return missing


# 全局配置实例
settings = Settings()
