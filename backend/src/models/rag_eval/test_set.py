import uuid
from datetime import datetime
from sqlalchemy import String, Text, DateTime, ForeignKey, func, Index, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.core.database import Base
from src.models.rag_eval.enums import RagEvalTestSetSourceType


class RagEvalTestSet(Base):
    __tablename__ = "rag_eval_test_sets"
    __table_args__ = (
        Index("idx_rag_eval_test_set_created_at", "created_at"),
        {"comment": "RAG评估测试集表"},
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    source_type: Mapped[RagEvalTestSetSourceType] = mapped_column(
        SAEnum(
            RagEvalTestSetSourceType, values_callable=lambda obj: [e.value for e in obj]
        ),
        nullable=False,
    )
    source_document_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("source_documents.id", ondelete="SET NULL"),
    )

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    source_document: Mapped["SourceDocument | None"] = relationship(
        foreign_keys=[source_document_id]
    )
    test_cases: Mapped[list["RagEvalTestSetCase"]] = relationship(
        back_populates="test_set", cascade="all, delete-orphan"
    )
    test_runs: Mapped[list["RagEvalTestRun"]] = relationship(
        back_populates="test_set", cascade="all, delete-orphan"
    )
    reports: Mapped[list["RagEvalTestReport"]] = relationship(
        back_populates="test_set", cascade="all, delete-orphan"
    )
    ignored_suggestions: Mapped[list["RagEvalIgnoredSuggestion"]] = relationship(
        back_populates="test_set", cascade="all, delete-orphan"
    )
