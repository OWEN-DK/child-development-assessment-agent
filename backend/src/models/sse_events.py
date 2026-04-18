"""SSE事件模型定义

定义RAG评估工作流中全部10种SSE事件的Pydantic模型。
所有事件通过SSEPublisher.publish()发布，消息格式统一为JSON对象，必须包含type字段标识事件类型。

注意：spec定义10种事件（9种业务事件 + 1种系统事件heartbeat）。
export_failed不是独立事件类型，而是导出失败时的错误处理场景。
"""

from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any, Union
from pydantic import BaseModel, Field


class SseEventType(str, Enum):
    """SSE事件类型枚举"""

    RUN_STARTED = "run_started"
    PROGRESS = "progress"
    CASE_RESULT = "case_result"
    TEST_COMPLETED = "test_completed"
    VALIDATION_STARTED = "validation_started"
    VALIDATION_COMPLETED = "validation_completed"
    REPORT_READY = "report_ready"
    RUN_FAILED = "run_failed"
    HEARTBEAT = "heartbeat"
    EXPORT_READY = "export_ready"
    EXPORT_FAILED = "export_failed"


class OverallMetrics(BaseModel):
    """集合指标"""

    precision: float
    recall: float
    f1: float
    mrr: float
    ndcg: float


class ValidationSummaryItem(BaseModel):
    """单层校验摘要"""

    status: str
    suggestion_count: Optional[int] = None


# ==================== 10种SSE事件模型 ====================


class RunStartedEvent(BaseModel):
    """测试开始事件"""

    type: str = Field(default=SseEventType.RUN_STARTED)
    run_id: str
    test_set_id: str
    total_cases: int
    config_version: Optional[str] = None
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")


class ProgressEvent(BaseModel):
    """进度事件"""

    type: str = Field(default=SseEventType.PROGRESS)
    run_id: str
    current_case: int
    total_cases: int
    current_query: Optional[str] = None
    elapsed_seconds: Optional[float] = None
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")


class CaseResultEvent(BaseModel):
    """单用例完成事件"""

    type: str = Field(default=SseEventType.CASE_RESULT)
    run_id: str
    case_id: str
    query: str
    hit_at_1: bool
    hit_at_3: bool
    hit_at_5: bool
    matched_doc_ids: List[str] = Field(default_factory=list)
    matched_doc_scores: List[float] = Field(default_factory=list)
    status: str  # "passed" 或 "failed"
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")


class TestCompletedEvent(BaseModel):
    """所有用例执行完毕事件"""

    type: str = Field(default=SseEventType.TEST_COMPLETED)
    run_id: str
    total_cases: int
    passed_cases: int
    overall_metrics: OverallMetrics
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")


class ValidationStartedEvent(BaseModel):
    """校验开始事件"""

    type: str = Field(default=SseEventType.VALIDATION_STARTED)
    run_id: str
    layer: int  # 1-6
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")


class ValidationCompletedEvent(BaseModel):
    """单层校验完成事件"""

    type: str = Field(default=SseEventType.VALIDATION_COMPLETED)
    run_id: str
    layer: int
    duration_ms: int
    suggestion_count: int
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")


class ReportReadyEvent(BaseModel):
    """报告就绪事件"""

    type: str = Field(default=SseEventType.REPORT_READY)
    run_id: str
    report_id: str
    overall_metrics: OverallMetrics
    total_duration_seconds: float
    validation_summary: Dict[str, ValidationSummaryItem]
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")


class RunFailedEvent(BaseModel):
    """测试失败事件"""

    type: str = Field(default=SseEventType.RUN_FAILED)
    run_id: str
    error_code: str
    error_message: str
    failed_at_case_id: Optional[str] = None
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")


class HeartbeatEvent(BaseModel):
    """心跳事件（系统级）"""

    type: str = Field(default=SseEventType.HEARTBEAT)
    run_id: str
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")


class ExportReadyEvent(BaseModel):
    """导出完成事件"""

    type: str = Field(default=SseEventType.EXPORT_READY)
    task_id: str
    report_id: str
    download_url: str
    file_size_bytes: int
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")


class ExportFailedEvent(BaseModel):
    """导出失败事件"""

    type: str = Field(default=SseEventType.EXPORT_FAILED)
    task_id: str
    report_id: str
    error: str
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")


# 联合类型，用于类型检查
SseEvent = Union[
    RunStartedEvent,
    ProgressEvent,
    CaseResultEvent,
    TestCompletedEvent,
    ValidationStartedEvent,
    ValidationCompletedEvent,
    ReportReadyEvent,
    RunFailedEvent,
    HeartbeatEvent,
    ExportReadyEvent,
    ExportFailedEvent,
]
