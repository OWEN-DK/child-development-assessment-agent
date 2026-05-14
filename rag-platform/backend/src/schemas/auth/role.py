"""角色相关实体类"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class PermissionItem(BaseModel):
    """权限项"""
    permission_code: str
    category: str
    description: str


class RoleCreate(BaseModel):
    """创建角色"""
    name: str = Field(min_length=1, max_length=100)
    permissions: list[str] = Field(min_length=1)


class RoleRead(BaseModel):
    """角色详情"""
    id: str
    name: str
    slug: str
    permissions: list[str]
    is_builtin: bool
    user_count: int = 0
    created_at: datetime


class RoleList(BaseModel):
    """角色列表"""
    items: list[RoleRead]
    total: int


class RoleUpdate(BaseModel):
    """更新角色"""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    permissions: Optional[list[str]] = None


class PermissionList(BaseModel):
    """可用权限列表"""
    permissions: list[PermissionItem]
