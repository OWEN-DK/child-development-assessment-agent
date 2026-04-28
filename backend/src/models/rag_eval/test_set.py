from datetime import datetime

from sqlalchemy import DateTime, Enum, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.models.rag_eval.enums import TestSourceType


class TestSet(Base):
    __tablename__ = "test_sets"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    source_type: Mapped[TestSourceType] = mapped_column(
        Enum(TestSourceType, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        default=TestSourceType.MANUAL,
        comment="manual/json_import/book_generated/mixed",
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = {"extend_existing": True}
