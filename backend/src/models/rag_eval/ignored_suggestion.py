import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime
from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database import Base
from src.models.rag_eval.enums import (RagEvalIgnoredSuggestionType,
                                       RagEvalIgnoreScope)


class RagEvalIgnoredSuggestion(Base):
    __tablename__ = "rag_eval_ignored_suggestions"
    __table_args__ = (
        Index(
            "idx_rag_eval_ignored_suggestion_testset_scope_restored",
            "test_set_id",
            "ignore_scope",
            "restored",
        ),
        Index("idx_rag_eval_ignored_suggestion_report", "report_id"),
        {"comment": "忽略的调优建议记录表"},
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )

    test_set_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("rag_eval_test_sets.id", ondelete="CASCADE"),
        nullable=False,
        comment="绑定测试集",
    )
    report_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("rag_eval_test_reports.id", ondelete="CASCADE"),
        comment="report级别时填写",
    )

    param_name: Mapped[str] = mapped_column(
        String(255), nullable=False, comment="参数名或prompt_key"
    )
    suggestion_type: Mapped[RagEvalIgnoredSuggestionType] = mapped_column(
        SAEnum(
            RagEvalIgnoredSuggestionType,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=False,
    )
    ignore_scope: Mapped[RagEvalIgnoreScope] = mapped_column(
        SAEnum(RagEvalIgnoreScope, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
    )

    ignored_by: Mapped[str | None] = mapped_column(String(36), comment="操作用户")
    ignored_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    ignore_reason: Mapped[str | None] = mapped_column(String(500))

    restored: Mapped[bool] = mapped_column(Boolean, default=False)
    restored_at: Mapped[datetime | None] = mapped_column(DateTime)

    test_set: Mapped["RagEvalTestSet"] = relationship(
        back_populates="ignored_suggestions"
    )
    report: Mapped["RagEvalTestReport | None"] = relationship(
        back_populates="ignored_suggestions"
    )
