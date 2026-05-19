"""LLM 调用日志与 A/B 测试指标数据模型"""
import enum
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (DECIMAL, JSON, Column, DateTime, Enum, Index, Integer, String, Text, func)

from src.models.base import Base


class LLMCallStatus(enum.Enum):
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"


class CallLevel(enum.Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


class LLMCallLog(Base):
    __tablename__ = "llm_call_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    request_id = Column(String(64), nullable=False, index=True)
    prompt_key = Column(String(255), index=True)
    prompt_version = Column(String(64))
    scenario = Column(String(100), index=True)
    model_name = Column(String(255), nullable=False, index=True)
    input_tokens = Column(Integer)
    output_tokens = Column(Integer)
    total_tokens = Column(Integer)
    duration_ms = Column(Integer, index=True)
    status = Column(
        Enum(LLMCallStatus, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        index=True,
    )
    error_message = Column(Text)
    created_at = Column(DateTime, server_default=func.now(), index=True)
    trace_id = Column(String(64), nullable=True)
    span_id = Column(String(64), nullable=True)
    parent_span_id = Column(String(64), nullable=True)
    prompt_messages = Column(JSON, nullable=True)
    completion_message = Column(Text, nullable=True)
    full_prompt_path = Column(String(512), nullable=True)
    full_completion_path = Column(String(512), nullable=True)
    call_parameters = Column(JSON, nullable=True)
    model_parameters = Column(JSON, nullable=True)
    cost = Column(DECIMAL(10, 4), nullable=True)
    tags = Column(JSON, nullable=True)
    tokens = Column(Integer, nullable=True)
    completion_start_time_ms = Column(Integer, nullable=True)
    level = Column(
        Enum(CallLevel, values_callable=lambda obj: [e.value for e in obj]),
        server_default="INFO",
        default=CallLevel.INFO,
    )
    user_id = Column(String(64), nullable=True)
    session_id = Column(String(64), nullable=True)

    __table_args__ = (
        Index("idx_span_id", "span_id", unique=True),
        Index("idx_llm_trace_id", "trace_id"),
    )


class ABTestMetrics(Base):
    __tablename__ = "ab_test_metrics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    test_name = Column(String(255), nullable=False, index=True)
    variant_name = Column(String(255), nullable=False, index=True)
    metric_value = Column(DECIMAL(10, 4), nullable=False)
    metric_type = Column(String(100), nullable=False)
    recorded_at = Column(DateTime, nullable=False, index=True)

    __table_args__ = (Index("idx_test_variant", "test_name", "variant_name"),)
