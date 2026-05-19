"""监控模块模型"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class TraceMetadata(BaseModel):
    """追踪元数据"""
    test_run_id: Optional[str] = Field(None, description="测试运行 ID")
    test_set_id: Optional[str] = Field(None, description="测试集 ID")
    test_case_id: Optional[str] = Field(None, description="测试用例 ID")
    document_id: Optional[str] = Field(None, description="文档 ID")
    model: Optional[str] = Field(None, description="使用的模型名称")
    provider: Optional[str] = Field(None, description="模型提供商")
    extra: Optional[dict] = Field(None, description="其他自定义字段")


class PerformanceMetrics(BaseModel):
    """性能指标"""
    avg_response_time_ms: float
    p95_response_time_ms: float
    p99_response_time_ms: float
    requests_per_second: float
    error_rate: float
    timestamp: datetime = Field(default_factory=datetime.now)
