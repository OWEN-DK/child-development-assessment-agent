"""评估报告 Schema"""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict

from src.schemas.rag_eval.diagnosis import LayerIssue


class OverallSummary(BaseModel):
    """报告总体摘要"""

    overall_score: float
    l1_score: float
    l2_score: float
    l3_score: float
    diagnosis_health: float
    total_issues: int
    critical_issues: int
    run_name: str
    total_cases: int
    passed_cases: int
    duration_ms: Optional[int] = None


class MetricCard(BaseModel):
    """指标卡片"""

    name: str
    value: float
    passed: bool
    threshold: float
    details: dict[str, Any] = {}
    delta: Optional[float] = None  # 与上次对比的变化值


class ScoringDashboard(BaseModel):
    """三层指标看板"""

    l1: list[MetricCard]
    l2: list[MetricCard]
    l3: list[MetricCard]


class DiagnosisSection(BaseModel):
    """诊断层 section"""

    layer: int
    name: str
    status: str
    score: float
    issues: list[LayerIssue]
    suggestions: list[str]


class BadCaseEntry(BaseModel):
    """坏案条目"""

    case_id: str
    query: str
    domain: str
    age: float
    expected_keywords: list[str]
    actual_answer: Optional[str] = None
    precision: Optional[float] = None
    recall: Optional[float] = None
    error_message: Optional[str] = None


class TuningEntry(BaseModel):
    """调优建议条目"""

    suggestion_id: str
    category: str
    severity: str
    title: str
    description: str
    current_value: Optional[Any] = None
    suggested_value: Optional[Any] = None
    expected_impact: Optional[str] = None
    conflict_with: Optional[str] = None


class EvalReportData(BaseModel):
    """完整报告数据（中间结构，不直接持久化）"""

    summary: OverallSummary
    scoring_dashboard: ScoringDashboard
    diagnosis_details: list[DiagnosisSection]
    bad_cases: list[BadCaseEntry]
    tuning_suggestions: list[TuningEntry]


class EvalReportRead(BaseModel):
    """报告读取 Schema"""

    id: str
    run_id: str
    test_set_id: Optional[str] = None
    config_version_id: Optional[str] = None
    status: str  # processing/completed/superseded
    summary: OverallSummary
    scoring_dashboard: ScoringDashboard
    diagnosis_details: list[DiagnosisSection]
    bad_cases: list[BadCaseEntry]
    tuning_suggestions: list[TuningEntry]
    markdown_content: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TrendData(BaseModel):
    """趋势数据"""

    run_ids: list[str]
    timestamps: list[datetime]
    overall_scores: list[float]
    metric_trends: dict[str, list[float]]  # {"context_precision": [0.7, 0.75, ...], ...}
    config_version_ids: list[Optional[str]]  # 每个 run 的配置版本
