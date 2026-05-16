"""搜索认证实体类"""
from pydantic import BaseModel, Field


class SearchAuthContext(BaseModel):
    """搜索认证上下文"""
    authenticated: bool = Field(default=False, description="是否已认证")
    user_id: str = Field(default="", description="用户ID")
    tenant_id: str = Field(default="", description="租户ID")
    roles: list[str] = Field(default_factory=list, description="用户权限列表")
    role_slugs: list[str] = Field(default_factory=list, description="用户角色标识列表")
    auth_method: str = Field(default="none", description="认证方式：jwt/api_key/none")
