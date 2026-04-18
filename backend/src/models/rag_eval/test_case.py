import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime
from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database import Base
from src.schemas import TestDomain


class RagEvalTestCase(Base):
    __tablename__ = "rag_eval_test_cases"
    __table_args__ = (
        Index("idx_rag_eval_test_case_domain_age", "domain", "age_months"),
        {"comment": "RAG评估测试用例表"},
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )

    query: Mapped[str] = mapped_column(Text, nullable=False)
    age_months: Mapped[int | None] = mapped_column(Integer)
    domain: Mapped[TestDomain] = mapped_column(
        SAEnum(TestDomain, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
    )

    expected_document_ids: Mapped[list] = mapped_column(
        JSON, default=list, comment="期望命中的文档ID列表"
    )
    expected_key_points: Mapped[list] = mapped_column(
        JSON, default=list, comment="期望知识点列表"
    )

    source_draft_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("rag_eval_test_case_drafts.id", ondelete="SET NULL"),
        comment="来源草稿ID",
    )

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    test_sets: Mapped[list["RagEvalTestSetCase"]] = relationship(
        back_populates="test_case", cascade="all, delete-orphan"
    )
    run_results: Mapped[list["RagEvalTestRunResult"]] = relationship(
        back_populates="test_case", cascade="all, delete-orphan"
    )
    intent_annotations: Mapped[list["RagEvalIntentAnnotation"]] = relationship(
        back_populates="test_case", cascade="all, delete-orphan"
    )
    source_draft: Mapped["RagEvalTestCaseDraft | None"] = relationship(
        back_populates="imported_test_cases"
    )
