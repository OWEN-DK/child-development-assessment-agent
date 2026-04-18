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
from src.models.rag_eval.enums import RagEvalTestRunStatus, RagEvalABTestSide


class RagEvalTestRun(Base):
    __tablename__ = "rag_eval_test_runs"
    __table_args__ = (
        Index(
            "idx_rag_eval_test_run_testset_status_created",
            "test_set_id",
            "status",
            "created_at",
        ),
        Index("idx_rag_eval_test_run_config_version", "config_version_id"),
        {"comment": "RAG评估测试运行记录表"},
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[RagEvalTestRunStatus] = mapped_column(
        SAEnum(
            RagEvalTestRunStatus, values_callable=lambda obj: [e.value for e in obj]
        ),
        nullable=False,
        default=RagEvalTestRunStatus.PENDING,
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

    created_by: Mapped[str | None] = mapped_column(
        String(36), comment="触发运行的用户ID"
    )

    overall_precision: Mapped[float | None] = mapped_column(Float)
    overall_recall: Mapped[float | None] = mapped_column(Float)
    overall_f1: Mapped[float | None] = mapped_column(Float)
    overall_mrr: Mapped[float | None] = mapped_column(Float)
    overall_ndcg: Mapped[float | None] = mapped_column(Float)

    total_test_cases: Mapped[int] = mapped_column(Integer, default=0)
    passed_test_cases: Mapped[int] = mapped_column(Integer, default=0)
    failed_at_case_id: Mapped[str | None] = mapped_column(
        String(36), comment="失败时的用例ID"
    )

    ab_test_id: Mapped[str | None] = mapped_column(String(36), comment="A/B测试组ID")
    ab_test_side: Mapped[RagEvalABTestSide | None] = mapped_column(
        SAEnum(RagEvalABTestSide, values_callable=lambda obj: [e.value for e in obj]),
        comment="标识本次运行是配置A还是配置B",
    )

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime, comment="仅在status=completed时填写"
    )

    test_set: Mapped["RagEvalTestSet"] = relationship(back_populates="test_runs")
    config_version: Mapped["RagEvalConfigVersion | None"] = relationship(
        back_populates="test_runs"
    )
    run_results: Mapped[list["RagEvalTestRunResult"]] = relationship(
        back_populates="test_run", cascade="all, delete-orphan"
    )
    reports: Mapped[list["RagEvalTestReport"]] = relationship(
        back_populates="test_run", cascade="all, delete-orphan"
    )
    intent_logs: Mapped[list["RagEvalQueryIntentLog"]] = relationship(
        back_populates="test_run", cascade="all, delete-orphan"
    )
