from datetime import datetime
from typing import Any

from sqlalchemy import (JSON, DateTime, Enum, Integer, String, Text,
                        func)
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.models.rag_eval.enums import DifficultyLevel


class TestCase(Base):
    __tablename__ = "test_cases"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    query: Mapped[str] = mapped_column(Text, nullable=False, comment="测试问题")
    description: Mapped[str | None] = mapped_column(Text, comment="期望答案描述")
    expected_knowledge_ids: Mapped[list[str] | None] = mapped_column(
        JSON, comment="期望检索的知识片段 ID 列表"
    )
    expected_keywords: Mapped[list[str] | None] = mapped_column(
        JSON, comment="期望关键词列表"
    )
    answer_points_summary: Mapped[str | None] = mapped_column(
        Text, comment="答案要点摘要"
    )
    difficulty_level: Mapped[DifficultyLevel | None] = mapped_column(
        Enum(DifficultyLevel, values_callable=lambda obj: [e.value for e in obj]),
        comment="easy/medium/hard",
    )
    professional_terms: Mapped[list[str] | None] = mapped_column(
        JSON, comment="专业术语列表"
    )
    relevance_scores: Mapped[dict[str, Any] | None] = mapped_column(
        JSON, comment="相关度评分"
    )
    book_ids: Mapped[list[str] | None] = mapped_column(
        JSON, comment="限定检索的书籍 file_hash 列表"
    )
    source: Mapped[str] = mapped_column(
        String(16), nullable=False, default="manual", index=True, comment="manual/draft/import"
    )
    source_draft_id: Mapped[str | None] = mapped_column(
        String(64), comment="来源草稿 ID"
    )
    source_document_id: Mapped[str | None] = mapped_column(
        String(64), comment="来源文档 ID"
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = {"extend_existing": True}
