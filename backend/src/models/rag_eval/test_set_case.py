from datetime import datetime

from sqlalchemy import DateTime, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base


class TestSetCase(Base):
    __tablename__ = "test_set_cases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    test_set_id: Mapped[str] = mapped_column(String(64), nullable=False)
    test_case_id: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True
    )
    added_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("test_set_id", "test_case_id", name="uk_set_case"),
        {"extend_existing": True},
    )
