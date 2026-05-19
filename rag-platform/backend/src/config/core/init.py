"""配置初始化模块

启动时校验、目录创建等。
"""
import logging
import os

logger = logging.getLogger(__name__)


def validate_required_env_vars() -> list[str]:
    """校验必需的环境变量是否已配置

    返回缺失的环境变量名称列表。
    """
    from src.config import settings

    missing = []

    settings_key = getattr(settings, "dashscope_api_key", None)
    env_key = os.environ.get("DASHSCOPE_API_KEY")
    if not settings_key and not env_key:
        missing.append("DASHSCOPE_API_KEY")

    env = os.getenv("ENVIRONMENT", "development")
    jwt_secret = os.getenv("JWT_SECRET", "")
    if env == "production" and (
        not jwt_secret or jwt_secret == "change-me-in-production-min-32-chars"
    ):
        missing.append("JWT_SECRET 必须在生产环境修改为安全值")

    return missing
