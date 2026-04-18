import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, ForeignKey, func, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.core.database import Base


class RagEvalIntentAnnotation(Base):
    __tablename__ = "rag_eval_intent_annotations"
    __table_args__ = (
        Index("uk_rag_eval_intent_annotation_case", "case_id", unique=True),
        {"comment": "测试用例意图标注表"},
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )

    case_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("rag_eval_test_cases.id", ondelete="CASCADE"),
        nullable=False,
    )

    intent_type: Mapped[str] = mapped_column(
        String(36),
        nullable=False,
        comment="如: factual_query, how_to, comparison, definition",
    )
    annotated_by: Mapped[str | None] = mapped_column(String(36), comment="标注人ID")
    annotated_at: Mapped[datetime | None] = mapped_column(DateTime)

    test_case: Mapped["RagEvalTestCase"] = relationship(
        back_populates="intent_annotations"
    )
