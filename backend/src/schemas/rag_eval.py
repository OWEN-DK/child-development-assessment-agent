"""RAG 评估相关 Pydantic Schema（实体类统一在 schemas/ 目录）"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ========== TestReport Schema ==========

class ValidationLayerResult(BaseModel):
    """单层校验结果"""
    status: str = Field(..., description="校验状态: pass/warning/fail")
    metrics: Optional[Dict[str, Any]] = Field(None, description="指标数据")
    suggestions: List["TuningSuggestionItem"] = Field(default_factory=list, description="调优建议")


class TuningSuggestionItem(BaseModel):
    """单个调优建议"""
    type: str = Field(..., description="建议类型: config/prompt/data")
    reason: str = Field(..., description="建议原因")
    current_value: Any = Field(..., description="当前值")
    suggested_value: Any = Field(..., description="建议值")
    impact_analysis: Dict[str, str] = Field(..., description="影响分析: {scope, expected_improvement, risk}")
    priority: str = Field(..., description="优先级: high/medium/low")


class TestReportCreate(BaseModel):
    """创建测试报告请求"""
    test_run_id: str = Field(..., description="测试运行 ID")
    validation_results: Dict[str, Any] = Field(..., description="6 层校验结果")
    tuning_suggestions: List[TuningSuggestionItem] = Field(..., description="调优建议列表")
    overall_score: float = Field(..., ge=0, le=100, description="综合评分 0-100")


class TestReportResponse(BaseModel):
    """测试报告响应"""
    id: str
    test_run_id: str
    validation_results: Dict[str, Any]
    tuning_suggestions: List[TuningSuggestionItem]
    overall_score: float
    generated_at: datetime

    class Config:
        from_attributes = True


# ========== TuningSuggestionRecord Schema ==========

class TuningSuggestionRecordCreate(BaseModel):
    """创建调优建议记录请求"""
    report_id: str = Field(..., description="报告 ID")
    suggestion_type: str = Field(..., description="建议类型: config/prompt/data")
    current_value: Any = Field(..., description="当前值")
    suggested_value: Any = Field(..., description="建议值")
    reason: str = Field(..., description="建议原因")
    impact_analysis: Dict[str, str] = Field(..., description="影响分析")


class TuningSuggestionRecordUpdate(BaseModel):
    """更新调优建议记录请求"""
    status: str = Field(..., description="新状态: pending/applied/ignored")
    applied_by: Optional[str] = Field(None, description="操作人")


class TuningSuggestionRecordResponse(BaseModel):
    """调优建议记录响应"""
    id: str
    report_id: str
    suggestion_type: str
    current_value: Any
    suggested_value: Any
    reason: str
    impact_analysis: Dict[str, str]
    status: str
    created_at: datetime
    applied_at: Optional[datetime] = None
    applied_by: Optional[str] = None

    class Config:
        from_attributes = True


# ========== IntentAnnotation Schema ==========

class IntentAnnotationCreate(BaseModel):
    """创建意图标注请求"""
    query: str = Field(..., max_length=500, description="用户查询文本")
    intent: str = Field(..., description="意图分类: factual/conceptual/procedural/comparative")
    expected_results: List[str] = Field(..., description="预期检索结果 ID 列表")
    confidence: Optional[float] = Field(None, ge=0, le=1, description="标注置信度 0-1")
    annotated_by: Optional[str] = Field(None, description="标注人")


class IntentAnnotationResponse(BaseModel):
    """意图标注响应"""
    id: str
    query: str
    intent: str
    expected_results: List[str]
    confidence: Optional[float] = None
    annotated_by: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


# ========== AuditLog Schema ==========

class AuditLogCreate(BaseModel):
    """创建审计日志请求"""
    operator: str = Field(..., max_length=100, description="操作人")
    action: str = Field(..., max_length=50, description="操作类型")
    target_type: str = Field(..., max_length=50, description="目标类型")
    target_id: str = Field(..., description="目标 ID")
    before_value: Optional[Dict[str, Any]] = Field(None, description="变更前值")
    after_value: Dict[str, Any] = Field(..., description="变更后值")
    diff_summary: Optional[str] = Field(None, description="变更摘要")
    ip_address: Optional[str] = Field(None, max_length=45, description="操作 IP")
    user_agent: Optional[str] = Field(None, max_length=500, description="用户代理")


class AuditLogResponse(BaseModel):
    """审计日志响应"""
    id: str
    operator: str
    action: str
    target_type: str
    target_id: str
    before_value: Optional[Dict[str, Any]] = None
    after_value: Dict[str, Any]
    diff_summary: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class AuditLogQueryParams(BaseModel):
    """审计日志查询参数"""
    operator: Optional[str] = Field(None, description="操作人筛选")
    action: Optional[str] = Field(None, description="操作类型筛选")
    target_type: Optional[str] = Field(None, description="目标类型筛选")
    target_id: Optional[str] = Field(None, description="目标 ID 筛选")
    from_date: Optional[datetime] = Field(None, description="开始时间")
    to_date: Optional[datetime] = Field(None, description="结束时间")
    page: int = Field(1, ge=1, description="页码")
    page_size: int = Field(20, ge=1, le=100, description="每页数量")


# 更新前向引用
ValidationLayerResult.model_rebuild()
