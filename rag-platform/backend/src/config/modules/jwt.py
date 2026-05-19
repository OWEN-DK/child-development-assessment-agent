"""JWT 认证配置"""
from pydantic import Field
from pydantic_settings import BaseSettings


class JWTSettings(BaseSettings):
    jwt_secret: str = Field(
        default="change-me-in-production-min-32-chars",
        validation_alias="JWT_SECRET",
        description="JWT 签名密钥",
    )
