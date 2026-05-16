"""调优建议与配置版本实体类"""
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


# ── 请求实体 ──────────────────────────────────────────

class AdoptSuggestionReq(BaseModel):
    """采纳调优建议请求"""
    suggestion_id: str = Field(..., description="建议ID")


# ── 响应实体 ──────────────────────────────────────────

class TuningSuggestionRead(BaseModel):
    """调优建议读取"""
    id: str
    run_id: str
    report_id: Optional[str] = None
    tenant_id: str
    category: str = Field(description="分类：retrieval/generation/system/permission")
    severity: str = Field(description="严重性：critical/warning/info")
    title: str
    description: Optional[str] = None
    current_value: Optional[str] = None
    suggested_value: Optional[str] = None
    expected_impact: Optional[str] = None
    source: str = "auto"
    priority: int = 5
    safe_range: Optional[str] = None
    conflict_with: Optional[list[str]] = None
    status: str = "pending"
    applied_config_version_id: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ConfigVersionRead(BaseModel):
    """评估配置版本读取"""
    id: str
    tenant_id: str
    version_number: int
    version_label: Optional[str] = None
    config_snapshot: dict[str, Any]
    change_summary: Optional[str] = None
    change_set_id: Optional[str] = None
    created_by: str
    created_at: datetime

    model_config = {"from_attributes": True}
