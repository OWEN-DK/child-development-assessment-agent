import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database import Base


class RagEvalQueryIntentLog(Base):
    __tablename__ = "rag_eval_query_intent_logs"
    __table_args__ = (
        Index("idx_rag_eval_query_intent_log_run", "run_id"),
        Index("idx_rag_eval_query_intent_log_case", "case_id"),
        {"comment": "查询意图自动分类日志表"},
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )

    run_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("rag_eval_test_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    case_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("rag_eval_test_cases.id", ondelete="CASCADE"),
    )

    query: Mapped[str] = mapped_column(Text, nullable=False)
    predicted_intent: Mapped[str] = mapped_column(
        String(36), nullable=False, comment="LLM自动分类的意图"
    )
    confidence: Mapped[float | None] = mapped_column(Float, comment="置信度(0.0-1.0)")

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    test_run: Mapped["RagEvalTestRun"] = relationship(back_populates="intent_logs")
    test_case: Mapped["RagEvalTestCase | None"] = relationship()
