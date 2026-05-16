"""测试集实体类"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# ── 请求实体 ──────────────────────────────────────────

class CreateTestSetReq(BaseModel):
    """创建测试集请求"""
    name: str = Field(..., min_length=1, max_length=255, description="测试集名称")
    description: Optional[str] = Field(default=None, description="描述")
    case_ids: list[str] = Field(default_factory=list, description="关联的用例ID列表（有序）")
    visibility: str = Field(default="public", description="可见性")


class UpdateTestSetReq(BaseModel):
    """更新测试集请求"""
    name: Optional[str] = Field(default=None, min_length=1, max_length=255, description="测试集名称")
    description: Optional[str] = Field(default=None, description="描述")
    case_ids: Optional[list[str]] = Field(default=None, description="关联的用例ID列表（有序）")


class AddCasesToSetReq(BaseModel):
    """向测试集添加用例请求"""
    case_ids: list[str] = Field(..., min_length=1, description="待添加的用例ID列表")


class RemoveCasesFromSetReq(BaseModel):
    """从测试集移除用例请求"""
    case_ids: list[str] = Field(..., min_length=1, description="待移除的用例ID列表")


# ── 响应实体 ──────────────────────────────────────────

class TestSetRead(BaseModel):
    """测试集读取"""
    id: str
    tenant_id: str
    name: str
    description: Optional[str] = None
    source_type: str = "manual"
    case_ids: Optional[list[str]] = None
    visibility: str = "public"
    owner_id: str
    created_at: datetime
    case_count: int = Field(default=0, description="关联用例数量（计算字段）")

    model_config = {"from_attributes": True}


class TestSetList(BaseModel):
    """测试集列表"""
    items: list[TestSetRead]
    total: int
