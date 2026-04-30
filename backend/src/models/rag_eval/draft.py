from datetime import datetime
from typing import Any

from sqlalchemy import (DECIMAL, JSON, DateTime, Enum, Integer, String, Text,
                        func)
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.models.rag_eval.enums import (DifficultyLevel, TestCaseStatus)


class TestCaseDraft(Base):
    __tablename__ = "test_case_drafts"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    source_document_id: Mapped[str | None] = mapped_column(
        String(64), index=True, comment="来源文档 ID"
    )
    query: Mapped[str] = mapped_column(Text, nullable=False, comment="测试问题")
    description: Mapped[str | None] = mapped_column(Text, comment="期望答案描述")
    expected_knowledge_ids: Mapped[list[str] | None] = mapped_column(
        JSON, comment="期望检索的知识片段 ID 列表"
    )
    expected_keywords: Mapped[list[str] | None] = mapped_column(
        JSON, comment="期望关键词列表"
    )
    answer_points: Mapped[list[str] | None] = mapped_column(
        JSON, comment="答案要点列表"
    )
    professional_terms: Mapped[list[str] | None] = mapped_column(
        JSON, comment="专业术语列表"
    )
    difficulty_level: Mapped[DifficultyLevel | None] = mapped_column(
        Enum(DifficultyLevel, values_callable=lambda obj: [e.value for e in obj]),
        comment="easy/medium/hard",
    )
    faithfulness_score: Mapped[float | None] = mapped_column(
        DECIMAL(5, 4), comment="忠实度评分(0-1)"
    )
    source_chunk_id: Mapped[str | None] = mapped_column(
        String(64), comment="来源分块 ID"
    )
    source_page: Mapped[int | None] = mapped_column(Integer, comment="来源页码")
    source_content_snippet: Mapped[str | None] = mapped_column(
        Text, comment="来源内容片段"
    )
    generation_params: Mapped[dict[str, Any] | None] = mapped_column(
        JSON, comment="生成参数快照"
    )
    batch_id: Mapped[str | None] = mapped_column(
        String(64), index=True, comment="生成批次 ID"
    )
    draft_index: Mapped[int] = mapped_column(
        Integer, default=0, comment="批次内序号"
    )
    status: Mapped[TestCaseStatus] = mapped_column(
        Enum(TestCaseStatus, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        default=TestCaseStatus.DRAFT,
        index=True,
        comment="draft/reviewed/rejected/imported",
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = {"extend_existing": True}
