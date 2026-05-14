"""用户相关实体类"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class UserCreate(BaseModel):
    """创建用户"""
    username: str = Field(min_length=1, max_length=100)
    email: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=6, max_length=128)
    roles: list[str] = Field(default_factory=list)


class UserRead(BaseModel):
    """用户详情"""
    id: str
    username: str
    email: str
    status: str
    roles: list[str] = Field(default_factory=list)
    created_at: datetime


class UserList(BaseModel):
    """用户列表"""
    items: list[UserRead]
    total: int


class UserInvite(BaseModel):
    """邀请用户"""
    email: str = Field(min_length=1, max_length=255)
    roles: list[str] = Field(min_length=1)


class UserAcceptInvitation(BaseModel):
    """接受邀请"""
    token: str
    password: str = Field(min_length=6, max_length=128)


class UserUpdate(BaseModel):
    """更新用户"""
    roles: Optional[list[str]] = None
    status: Optional[str] = None
