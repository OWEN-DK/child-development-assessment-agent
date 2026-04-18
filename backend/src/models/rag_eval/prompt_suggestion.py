import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime
from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database import Base
from src.models.rag_eval.enums import RagEvalPromptSuggestionType


class RagEvalPromptSuggestionRecord(Base):
    __tablename__ = "rag_eval_prompt_suggestion_records"
    __table_args__ = (
        Index("idx_rag_eval_prompt_suggestion_report_applied", "report_id", "applied"),
        {"comment": "提示词调优建议记录表"},
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )

    report_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("rag_eval_test_reports.id", ondelete="CASCADE"),
        nullable=False,
    )
    prompt_key: Mapped[str] = mapped_column(String(128), nullable=False)
    current_version_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("rag_eval_prompt_versions.id", ondelete="SET NULL"),
    )
    suggested_version_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("rag_eval_prompt_versions.id", ondelete="SET NULL"),
    )

    reason: Mapped[str | None] = mapped_column(Text)
    expected_effect: Mapped[str | None] = mapped_column(String(255))
    priority: Mapped[str | None] = mapped_column(String(32))
    source: Mapped[str | None] = mapped_column(String(36))
    suggestion_type: Mapped[RagEvalPromptSuggestionType | None] = mapped_column(
        SAEnum(
            RagEvalPromptSuggestionType,
            values_callable=lambda obj: [e.value for e in obj],
        ),
    )
    applied: Mapped[bool] = mapped_column(Boolean, default=False)
    applied_version_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("rag_eval_prompt_versions.id", ondelete="SET NULL"),
    )

    report: Mapped["RagEvalTestReport"] = relationship(
        back_populates="prompt_suggestions"
    )
    current_prompt_version: Mapped["RagEvalPromptVersion | None"] = relationship(
        foreign_keys=[current_version_id]
    )
    suggested_prompt_version: Mapped["RagEvalPromptVersion | None"] = relationship(
        foreign_keys=[suggested_version_id]
    )
    applied_prompt_version: Mapped["RagEvalPromptVersion | None"] = relationship(
        foreign_keys=[applied_version_id]
    )
