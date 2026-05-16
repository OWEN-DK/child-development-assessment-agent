"""评估报告实体类"""
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


# ── 请求实体 ──────────────────────────────────────────

class CreateReportReq(BaseModel):
    """创建评估报告请求"""
    run_id: str = Field(..., description="运行ID")
    force: bool = Field(default=False, description="是否强制重新生成")


# ── 响应实体 ──────────────────────────────────────────

class ReportRead(BaseModel):
    """评估报告读取"""
    id: str
    run_id: str
    tenant_id: str
    overall_score: Optional[float] = None
    l1_score: Optional[float] = None
    l2_score: Optional[float] = None
    l3_score: Optional[float] = None
    cross_domain_score: Optional[float] = None
    metrics_json: Optional[dict[str, Any]] = None
    diagnosis_json: Optional[dict[str, Any]] = None
    bad_cases_json: Optional[dict[str, Any]] = None
    suggestions_json: Optional[dict[str, Any]] = None
    cross_domain_json: Optional[dict[str, Any]] = None
    markdown_content: Optional[str] = None
    status: str = "processing"
    created_at: datetime

    model_config = {"from_attributes": True}


class ReportList(BaseModel):
    """评估报告列表"""
    items: list[ReportRead]
    total: int
