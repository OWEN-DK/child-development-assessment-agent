from sqlalchemy import String, Text, DateTime, JSON, Boolean, Float, func, Index
from sqlalchemy.orm import Mapped, mapped_column
from src.core.database import Base
from datetime import datetime


class PromptVersion(Base):
    __tablename__ = "prompt_versions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    prompt_key: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    version: Mapped[str] = mapped_column(String(64), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[str | None] = mapped_column(String(64))
    variables: Mapped[list | None] = mapped_column(JSON)
    tags: Mapped[list | None] = mapped_column(JSON)
    fallback: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("idx_prompt_key_version", "prompt_key", "version", unique=True),
    )


class PromptABTest(Base):
    __tablename__ = "prompt_ab_tests"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    prompt_key: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    variant_a_version: Mapped[str] = mapped_column(String(64), nullable=False)
    variant_b_version: Mapped[str] = mapped_column(String(64), nullable=False)
    variant_a_ratio: Mapped[float] = mapped_column(Float, default=0.5)
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (Index("idx_ab_test_prompt", "prompt_key", "is_active"),)
