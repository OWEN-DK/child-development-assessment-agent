from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base


class TuningSuggestion(Base):
    __tablename__ = "tuning_suggestions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    report_id: Mapped[str | None] = mapped_column(
        String(64), index=True, comment="关联报告 ID"
    )
    category: Mapped[str] = mapped_column(
        String(32), nullable=False, index=True, comment="retrieval/generation/configuration/cost/prompt"
    )
    severity: Mapped[str] = mapped_column(
        String(16), nullable=False, comment="critical/warning/info"
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    current_value: Mapped[dict[str, Any] | None] = mapped_column(
        JSON, comment="当前值"
    )
    suggested_value: Mapped[dict[str, Any] | None] = mapped_column(
        JSON, comment="建议值"
    )
    expected_impact: Mapped[str | None] = mapped_column(Text, comment="预期影响")
    source: Mapped[str] = mapped_column(
        String(16), nullable=False, default="rule_engine", comment="rule_engine/llm/diagnosis"
    )
    priority: Mapped[int] = mapped_column(
        Integer, default=0, comment="优先级（数值越高越优先）"
    )
    safe_range: Mapped[dict[str, Any] | None] = mapped_column(
        JSON, comment="安全范围"
    )
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="pending", index=True, comment="pending/adopted/rejected/ignored"
    )
    conflict_with: Mapped[str | None] = mapped_column(
        String(64), comment="冲突的建议 ID"
    )
    applied_config_version_id: Mapped[str | None] = mapped_column(
        String(64), comment="采纳后生成的配置版本 ID"
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = {"extend_existing": True}
