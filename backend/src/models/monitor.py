from sqlalchemy import String, Integer, DateTime, DECIMAL, Enum, func, Index, Text
from sqlalchemy.orm import Mapped, mapped_column
from src.core.database import Base
from datetime import datetime
from enum import Enum as PyEnum


class LLMCallStatus(PyEnum):
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"


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
