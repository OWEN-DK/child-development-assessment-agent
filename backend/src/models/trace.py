"""Trace 数据模型

用于表示一次完整的工作流执行（如一次评估请求、一次测试运行），
与 LLMCallLog 建立一对多关系。
"""

import enum
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (DECIMAL, JSON, DateTime, Enum, Index, Integer, String,
                        func, text)
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base


class TraceStatus(enum.Enum):
    SUCCESS = "success"
    FAILED = "failed"
    PARTIAL = "partial"


class Trace(Base):
    __tablename__ = "traces"

    trace_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    user_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    session_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    trace_metadata: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)
    start_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    end_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    total_duration_ms: Mapped[int] = mapped_column(
        Integer, server_default=text("0"), default=0
    )
    total_tokens: Mapped[int] = mapped_column(
        Integer, server_default=text("0"), default=0
    )
    total_cost: Mapped[Decimal] = mapped_column(
        DECIMAL(10, 4), server_default=text("0.0000"), default=Decimal("0.0000")
    )
    status: Mapped[TraceStatus] = mapped_column(
        Enum(TraceStatus, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("idx_user_id", "user_id"),
        Index("idx_created_at", "created_at"),
        Index("idx_trace_status", "status", "created_at"),
    )
