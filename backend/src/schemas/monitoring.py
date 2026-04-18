"""监控模块模型

包含系统监控相关的 Pydantic 模型：
- TraceMetadata: 追踪元数据
- MetricData: 指标数据
- 等监控 DTO
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class TraceMetadata(BaseModel):
    """追踪元数据"""

    child_profile_id: Optional[str] = Field(None, description="儿童档案 ID")
    test_run_id: Optional[str] = Field(None, description="测试运行 ID")
    test_set_id: Optional[str] = Field(None, description="测试集 ID")
    test_case_id: Optional[str] = Field(None, description="测试用例 ID")
    document_id: Optional[str] = Field(None, description="文档 ID")
    model: Optional[str] = Field(None, description="使用的模型名称")
    provider: Optional[str] = Field(None, description="模型提供商")
    extra: Optional[dict] = Field(None, description="其他自定义字段")


class MetricData(BaseModel):
    """指标数据"""

    name: str
    value: float
    timestamp: datetime
    labels: Dict[str, str] = Field(default_factory=dict)
    unit: Optional[str] = None


class HealthCheckResponse(BaseModel):
    """健康检查响应"""

    status: str
    services: Dict[str, bool] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.now)


class PerformanceMetrics(BaseModel):
    """性能指标"""

    avg_response_time_ms: float
    p95_response_time_ms: float
    p99_response_time_ms: float
    requests_per_second: float
    error_rate: float
    timestamp: datetime = Field(default_factory=datetime.now)
