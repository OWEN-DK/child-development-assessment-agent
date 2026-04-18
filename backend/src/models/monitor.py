from sqlalchemy import String, Integer, DateTime, DECIMAL, Enum, func, Index, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column
from src.core.database import Base
from datetime import datetime
from enum import Enum as PyEnum
from decimal import Decimal


class LLMCallStatus(PyEnum):
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"


class CallLevel(PyEnum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


class ABTestMetrics(Base):
    __tablename__ = "ab_test_metrics"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    test_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    variant_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    metric_value: Mapped[float] = mapped_column(DECIMAL(10, 4), nullable=False)
    metric_type: Mapped[str] = mapped_column(String(100), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)

    __table_args__ = (Index("idx_test_variant", "test_name", "variant_name"),)


class LLMCallLog(Base):
    __tablename__ = "llm_call_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    request_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    prompt_key: Mapped[str | None] = mapped_column(String(255), index=True)
    prompt_version: Mapped[str | None] = mapped_column(String(64))
    scenario: Mapped[str | None] = mapped_column(String(100), index=True)
    model_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)

    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    total_tokens: Mapped[int | None] = mapped_column(Integer)
    duration_ms: Mapped[int | None] = mapped_column(Integer, index=True)

    status: Mapped[LLMCallStatus] = mapped_column(
        Enum(LLMCallStatus, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        index=True,
    )
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), index=True
    )

    # Trace/Span 扩展字段
    trace_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    span_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    parent_span_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    prompt_messages: Mapped[list | None] = mapped_column(JSON, nullable=True)
    completion_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    full_prompt_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    full_completion_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    call_parameters: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    model_parameters: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    cost: Mapped[Decimal | None] = mapped_column(DECIMAL(10, 4), nullable=True)
    tags: Mapped[list | None] = mapped_column(JSON, nullable=True)
    tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completion_start_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    level: Mapped[CallLevel] = mapped_column(
        Enum(CallLevel, values_callable=lambda obj: [e.value for e in obj]),
        server_default="INFO",
        default=CallLevel.INFO,
    )
    user_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    session_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    __table_args__ = (
        Index("idx_span_id", "span_id", unique=True),
        Index("idx_llm_trace_id", "trace_id"),
    )
