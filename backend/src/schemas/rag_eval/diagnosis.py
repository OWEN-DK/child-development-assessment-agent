"""六层诊断 Schema"""

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel


class LayerIssue(BaseModel):
    """单个诊断问题"""

    severity: Literal["critical", "warning", "info"]
    category: str  # 问题类别
    description: str  # 问题描述
    affected_items: list[str] = []  # 受影响的用例/文档 ID
    suggestion: Optional[str] = None  # 修复建议


class LayerResult(BaseModel):
    """单层诊断结果"""

    layer: int  # 1-6
    name: str  # 层名称
    status: Literal["pass", "warn", "fail", "skip", "error"]
    score: float  # 0-1，该层健康度
    issues: list[LayerIssue] = []
    details: dict[str, Any] = {}
    execution_time_ms: int = 0


class DiagnosisResult(BaseModel):
    """六层诊断完整结果"""

    layer1: LayerResult
    layer2: LayerResult
    layer3: LayerResult
    layer4: LayerResult
    layer5: LayerResult
    layer6: LayerResult
    overall_health: float  # 0-1，综合健康度
    total_issues: int
    critical_issues: int
    diagnosed_at: datetime
