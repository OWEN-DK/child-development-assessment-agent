"""租户相关实体类"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class AdminUserCreate(BaseModel):
    """初始管理员用户"""
    username: str = Field(min_length=1, max_length=100)
    email: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=6, max_length=128)


class QuotaConfig(BaseModel):
    """配额配置"""
    max_knowledge_bases: int = Field(default=10, ge=1)
    max_documents: int = Field(default=1_000_000, ge=1)
    max_users: int = Field(default=100, ge=1)
    max_storage_gb: int = Field(default=50, ge=1)
    max_search_qps: int = Field(default=50, ge=1)
    max_concurrent_eval_runs: int = Field(default=2, ge=1)


class TenantCreate(BaseModel):
    """创建租户请求"""
    name: str = Field(min_length=1, max_length=255)
    slug: str = Field(min_length=1, max_length=100, pattern=r"^[a-z0-9\-]+$")
    admin_user: AdminUserCreate
    quotas: QuotaConfig = Field(default_factory=QuotaConfig)


class TenantRead(BaseModel):
    """租户详情"""
    id: str
    name: str
    slug: str
    status: str
    resource_limits: Optional[dict] = None
    user_count: int = 0
    storage_usage_gb: float = 0.0
    created_at: datetime
    updated_at: datetime


class TenantList(BaseModel):
    """租户列表"""
    items: list[TenantRead]
    total: int


class TenantUpdate(BaseModel):
    """更新租户"""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    status: Optional[str] = None
    resource_limits: Optional[QuotaConfig] = None


class QuotaUsage(BaseModel):
    """配额使用情况"""
    tenant_id: str
    knowledge_bases: int = 0
    knowledge_bases_limit: int = 10
    documents: int = 0
    documents_limit: int = 1_000_000
    users: int = 0
    users_limit: int = 100
    storage_gb: float = 0.0
    storage_limit_gb: float = 50.0
