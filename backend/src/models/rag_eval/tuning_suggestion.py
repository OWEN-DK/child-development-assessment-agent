import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime
from sqlalchemy import Enum as SAEnum
from sqlalchemy import Float, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database import Base
from src.models.rag_eval.enums import RagEvalSuggestionSource


class RagEvalTuningSuggestionRecord(Base):
    __tablename__ = "rag_eval_tuning_suggestion_records"
    __table_args__ = (
        Index("idx_rag_eval_tuning_suggestion_report_applied", "report_id", "applied"),
        {"comment": "参数调优建议记录表"},
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )

    report_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("rag_eval_test_reports.id", ondelete="CASCADE"),
        nullable=False,
    )

    param_name: Mapped[str] = mapped_column(String(128), nullable=False)
    current_value: Mapped[dict | None] = mapped_column(JSON)
    suggested_value: Mapped[dict | None] = mapped_column(JSON)
    action: Mapped[str | None] = mapped_column(String(36))
    reason: Mapped[str | None] = mapped_column(Text)
    expected_effect: Mapped[dict | None] = mapped_column(JSON, comment="预期效果")
    priority: Mapped[str | None] = mapped_column(String(32))
    source: Mapped[RagEvalSuggestionSource | None] = mapped_column(
        SAEnum(
            RagEvalSuggestionSource, values_callable=lambda obj: [e.value for e in obj]
        ),
    )
    safe_range: Mapped[dict | None] = mapped_column(JSON, comment="安全范围")
    applied: Mapped[bool] = mapped_column(Boolean, default=False)
    applied_config_version_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("rag_eval_config_versions.id", ondelete="SET NULL"),
        comment="采纳后应用到的配置版本ID",
    )

    report: Mapped["RagEvalTestReport"] = relationship(
        back_populates="tuning_suggestions"
    )
    applied_config_version: Mapped["RagEvalConfigVersion | None"] = relationship()
