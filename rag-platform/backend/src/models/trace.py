"""Trace 数据模型"""
import enum
from datetime import datetime
from decimal import Decimal

from sqlalchemy import JSON, DECIMAL, Column, DateTime, Enum, Index, Integer, String, func, text

from src.models.base import Base


class TraceStatus(enum.Enum):
    SUCCESS = "success"
    FAILED = "failed"
    PARTIAL = "partial"


class Trace(Base):
    __tablename__ = "traces"

    trace_id = Column(String(64), primary_key=True)
    name = Column(String(255), nullable=False)
    user_id = Column(String(64), nullable=True)
    session_id = Column(String(64), nullable=True)
    trace_metadata = Column("metadata", JSON, nullable=True)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=True)
    total_duration_ms = Column(Integer, server_default=text("0"), default=0)
    total_tokens = Column(Integer, server_default=text("0"), default=0)
    total_cost = Column(DECIMAL(10, 4), server_default=text("0.0000"), default=Decimal("0.0000"))
    status = Column(
        Enum(TraceStatus, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
    )
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("idx_user_id", "user_id"),
        Index("idx_created_at", "created_at"),
        Index("idx_trace_status", "status", "created_at"),
    )
