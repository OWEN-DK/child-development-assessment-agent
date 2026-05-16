"""速率限制实体类"""
from pydantic import BaseModel, Field


class RateLimitResult(BaseModel):
    """速率限制检查结果"""
    allowed: bool = Field(description="是否允许通过")
    remaining: int = Field(default=0, description="剩余配额")
    reset_after_ms: int = Field(default=0, description="重置等待时间（毫秒）")
    limit_type: str = Field(default="pipeline", description="限制类型：pipeline")
