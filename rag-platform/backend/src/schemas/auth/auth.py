"""认证相关实体类"""
from pydantic import BaseModel, Field

from src.schemas.auth.user import UserRead
from src.schemas.auth.tenant import TenantRead


class LoginRequest(BaseModel):
    """登录请求"""
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=128)


class LoginResponse(BaseModel):
    """登录响应"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserRead
    tenant: TenantRead | None = None


class TokenRefresh(BaseModel):
    """刷新令牌请求"""
    refresh_token: str


class TokenRefreshResponse(BaseModel):
    """刷新令牌响应"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class SwitchRoleRequest(BaseModel):
    """切换角色视角请求"""
    role: str = Field(description="要切换到的角色")
