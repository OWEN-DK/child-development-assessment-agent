import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database import Base


class RagEvalTestSetCase(Base):
    __tablename__ = "rag_eval_test_set_cases"
    __table_args__ = (
        Index("idx_rag_eval_test_set_case_test_set", "test_set_id"),
        Index("idx_rag_eval_test_set_case_case", "case_id"),
        Index("uk_rag_eval_test_set_case", "test_set_id", "case_id", unique=True),
        {"comment": "测试集-测试用例关联表"},
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )

    test_set_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("rag_eval_test_sets.id", ondelete="CASCADE"),
        nullable=False,
    )
    case_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("rag_eval_test_cases.id", ondelete="CASCADE"),
        nullable=False,
    )

    added_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    added_by: Mapped[str | None] = mapped_column(String(36), comment="添加用例的用户ID")

    test_set: Mapped["RagEvalTestSet"] = relationship(back_populates="test_cases")
    test_case: Mapped["RagEvalTestCase"] = relationship(back_populates="test_sets")
