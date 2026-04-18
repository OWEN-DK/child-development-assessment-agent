import uuid
from datetime import datetime
from sqlalchemy import (
    String,
    Text,
    DateTime,
    Integer,
    JSON,
    ForeignKey,
    func,
    Index,
    Enum as SAEnum,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.core.database import Base
from src.models.rag_eval.enums import RagEvalTestCaseDraftStatus
from src.models.test_case import TestDomain


class RagEvalTestCaseDraft(Base):
    __tablename__ = "rag_eval_test_case_drafts"
    __table_args__ = (
        Index(
            "idx_rag_eval_test_case_draft_doc_status", "source_document_id", "status"
        ),
        {"comment": "测试用例草稿表"},
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )

    source_document_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("source_documents.id", ondelete="CASCADE"),
        nullable=False,
    )

    query: Mapped[str] = mapped_column(Text, nullable=False)
    age_months: Mapped[int | None] = mapped_column(Integer)
    domain: Mapped[TestDomain] = mapped_column(
        SAEnum(TestDomain, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
    )
    expected_key_points: Mapped[list] = mapped_column(
        JSON, default=list, comment="期望知识点列表"
    )

    status: Mapped[RagEvalTestCaseDraftStatus] = mapped_column(
        SAEnum(
            RagEvalTestCaseDraftStatus,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=False,
        default=RagEvalTestCaseDraftStatus.DRAFT,
    )
    reviewed_by: Mapped[str | None] = mapped_column(String(36), comment="审核人ID")
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    source_document: Mapped["SourceDocument"] = relationship(
        foreign_keys=[source_document_id]
    )
    imported_test_cases: Mapped[list["RagEvalTestCase"]] = relationship(
        back_populates="source_draft"
    )
