import uuid
from datetime import datetime
from sqlalchemy import (
    String,
    Text,
    DateTime,
    Integer,
    Float,
    JSON,
    ForeignKey,
    func,
    Index,
    Enum as SAEnum,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.core.database import Base
from src.models.rag_eval.enums import RagEvalTestReportStatus


class RagEvalTestReport(Base):
    __tablename__ = "rag_eval_test_reports"
    __table_args__ = (
        Index("idx_rag_eval_test_report_testset_created", "test_set_id", "created_at"),
        Index("idx_rag_eval_test_report_run_id", "run_id"),
        Index("idx_rag_eval_test_report_config_version", "config_version_id"),
        {"comment": "测试评估报告表"},
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )

    run_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("rag_eval_test_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    test_set_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("rag_eval_test_sets.id", ondelete="CASCADE"),
        nullable=False,
    )
    config_version_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("rag_eval_config_versions.id", ondelete="SET NULL"),
    )

    status: Mapped[RagEvalTestReportStatus] = mapped_column(
        SAEnum(
            RagEvalTestReportStatus, values_callable=lambda obj: [e.value for e in obj]
        ),
        nullable=False,
        default=RagEvalTestReportStatus.PROCESSING,
    )
    prompt_version_snapshot: Mapped[dict | None] = mapped_column(
        JSON, comment="提示词版本快照"
    )

    overall_score: Mapped[float | None] = mapped_column(Float)
    precision: Mapped[float | None] = mapped_column(Float)
    recall: Mapped[float | None] = mapped_column(Float)
    f1: Mapped[float | None] = mapped_column(Float)
    mrr: Mapped[float | None] = mapped_column(Float)
    ndcg: Mapped[float | None] = mapped_column(Float)

    validation_results: Mapped[list | None] = mapped_column(JSON, comment="6层校验结果")
    tuning_suggestion_summary: Mapped[dict | None] = mapped_column(
        JSON, comment="调优建议摘要"
    )

    created_by: Mapped[str | None] = mapped_column(
        String(36), comment="生成报告的用户ID"
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    test_run: Mapped["RagEvalTestRun"] = relationship(back_populates="reports")
    test_set: Mapped["RagEvalTestSet"] = relationship(back_populates="reports")
    config_version: Mapped["RagEvalConfigVersion | None"] = relationship(
        back_populates="reports"
    )
    tuning_suggestions: Mapped[list["RagEvalTuningSuggestionRecord"]] = relationship(
        back_populates="report", cascade="all, delete-orphan"
    )
    prompt_suggestions: Mapped[list["RagEvalPromptSuggestionRecord"]] = relationship(
        back_populates="report", cascade="all, delete-orphan"
    )
    ignored_suggestions: Mapped[list["RagEvalIgnoredSuggestion"]] = relationship(
        back_populates="report", cascade="all, delete-orphan"
    )
