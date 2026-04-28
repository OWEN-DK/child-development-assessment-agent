from datetime import datetime
from typing import Any

from sqlalchemy import (DECIMAL, JSON, DateTime, Enum, Integer, String, Text,
                        func)
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base


class EvalReport(Base):
    __tablename__ = "eval_reports"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    test_set_id: Mapped[str | None] = mapped_column(
        String(64), index=True, comment="主测试集 ID"
    )
    config_version_id: Mapped[str | None] = mapped_column(
        String(64), comment="配置版本 ID"
    )
    overall_score: Mapped[float | None] = mapped_column(
        DECIMAL(5, 4), comment="三层加权综合得分"
    )
    l1_score: Mapped[float | None] = mapped_column(DECIMAL(5, 4), comment="L1 层得分")
    l2_score: Mapped[float | None] = mapped_column(DECIMAL(5, 4), comment="L2 层得分")
    l3_score: Mapped[float | None] = mapped_column(DECIMAL(5, 4), comment="L3 层得分")
    precision: Mapped[float | None] = mapped_column(DECIMAL(5, 4))
    recall: Mapped[float | None] = mapped_column(DECIMAL(5, 4))
    f1: Mapped[float | None] = mapped_column(DECIMAL(5, 4))
    mrr: Mapped[float | None] = mapped_column(DECIMAL(5, 4))
    ndcg: Mapped[float | None] = mapped_column(DECIMAL(5, 4))
    metrics_json: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, comment="三层指标 RunMetrics JSON"
    )
    diagnosis_json: Mapped[dict[str, Any] | None] = mapped_column(
        JSON, comment="六层诊断结果 JSON"
    )
    bad_cases_json: Mapped[list[dict[str, Any]] | None] = mapped_column(
        JSON, comment="坏案列表 JSON"
    )
    suggestions_json: Mapped[list[dict[str, Any]] | None] = mapped_column(
        JSON, comment="调优建议列表 JSON"
    )
    markdown_content: Mapped[str | None] = mapped_column(
        "markdown_content", Text, comment="Markdown 报告内容"
    )
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="processing", comment="processing/completed/superseded"
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = {"extend_existing": True}
