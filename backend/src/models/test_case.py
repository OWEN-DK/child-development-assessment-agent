from datetime import datetime
from enum import Enum as PyEnum
from typing import Any, List, Optional, Tuple

from pydantic import BaseModel
from sqlalchemy import (DECIMAL, JSON, DateTime, Enum, ForeignKey, Index,
                        Integer, String, Text, func)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database import Base
# Re-export SourceDocument from document module to avoid duplicate class registration
from src.models.document import DocumentStatus, SourceDocument


class TestDomain(PyEnum):
    GROSS_MOTOR = "gross_motor"
    FINE_MOTOR = "fine_motor"
    LANGUAGE = "language"
    COGNITIVE = "cognitive"
    SOCIAL_EMOTIONAL = "social_emotional"
    SENSORY_INTEGRATION = "sensory_integration"


class DifficultyLevel(PyEnum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class TestCaseStatus(PyEnum):
    DRAFT = "draft"
    REVIEWED = "reviewed"
    REJECTED = "rejected"
    IMPORTED = "imported"


# Alias for backward compatibility
DraftStatus = TestCaseStatus


class TestRunStatus(PyEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TestSourceType(PyEnum):
    MANUAL = "manual"
    JSON_IMPORT = "json_import"
    BOOK_GENERATED = "book_generated"
    MIXED = "mixed"


class ReportExportFormat(PyEnum):
    MARKDOWN = "markdown"
    PDF = "pdf"
    JSON = "json"


class DocumentStatus(PyEnum):
    UPLOADED = "uploaded"
    PARSING = "parsing"
    READY = "ready"
    ARCHIVED = "archived"


class KnowledgeSnapshot(Base):
    __tablename__ = "knowledge_snapshots"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    vector_store_path: Mapped[str] = mapped_column(String(512), nullable=False)
    document_count: Mapped[int] = mapped_column(Integer, default=0)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class TestCase(Base):
    __tablename__ = "test_cases"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    query: Mapped[str] = mapped_column(Text, nullable=False)
    age: Mapped[float] = mapped_column(DECIMAL(4, 1), nullable=False)
    domain: Mapped[TestDomain] = mapped_column(
        Enum(TestDomain, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
    )
    description: Mapped[str | None] = mapped_column(Text)

    expected_knowledge_count: Mapped[int] = mapped_column(Integer, default=0)
    answer_points_summary: Mapped[str | None] = mapped_column(Text)
    min_age_requirement: Mapped[float | None] = mapped_column(DECIMAL(4, 1))
    max_age_requirement: Mapped[float | None] = mapped_column(DECIMAL(4, 1))
    difficulty_level: Mapped[DifficultyLevel | None] = mapped_column(
        Enum(DifficultyLevel, values_callable=lambda obj: [e.value for e in obj])
    )

    expected_knowledge_ids: Mapped[list[str] | None] = mapped_column(JSON)
    expected_keywords: Mapped[list[str] | None] = mapped_column(JSON)
    professional_terms: Mapped[list[str] | None] = mapped_column(JSON)
    relevance_scores: Mapped[dict[str, float] | None] = mapped_column(JSON)

    source_document_id: Mapped[str | None] = mapped_column(String(64))
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index("idx_domain", "domain"),
        Index("idx_age", "age"),
        Index("idx_difficulty", "difficulty_level"),
        Index("idx_age_range", "min_age_requirement", "max_age_requirement"),
        Index("idx_source_doc", "source_document_id"),
    )


class TestCaseDraft(Base):
    __tablename__ = "test_case_drafts"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    source_document_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("source_documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    query: Mapped[str] = mapped_column(Text, nullable=False)
    age: Mapped[float] = mapped_column(DECIMAL(4, 1), nullable=False)
    domain: Mapped[TestDomain] = mapped_column(
        Enum(TestDomain, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
    )
    description: Mapped[str | None] = mapped_column(Text)

    generation_batch_id: Mapped[str | None] = mapped_column(String(64), index=True)

    expected_knowledge_ids: Mapped[list[str] | None] = mapped_column(JSON)
    expected_keywords: Mapped[list[str] | None] = mapped_column(JSON)
    answer_points: Mapped[list[str] | None] = mapped_column(JSON)
    professional_terms: Mapped[list[str] | None] = mapped_column(JSON)
    age_requirement: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    generation_params: Mapped[dict[str, Any] | None] = mapped_column(JSON)

    status: Mapped[TestCaseStatus] = mapped_column(
        Enum(TestCaseStatus, values_callable=lambda obj: [e.value for e in obj]),
        default=TestCaseStatus.DRAFT,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index("idx_source_doc", "source_document_id"),
        Index("idx_domain_status", "domain", "status"),
        Index("idx_generation_batch", "generation_batch_id"),
    )


class TestSet(Base):
    __tablename__ = "test_sets"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    source_type: Mapped[TestSourceType] = mapped_column(
        Enum(TestSourceType, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class TestSetCase(Base):
    __tablename__ = "test_set_cases"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    test_set_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("test_sets.id", ondelete="CASCADE"), nullable=False
    )
    test_case_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("test_cases.id", ondelete="CASCADE"), nullable=False
    )
    added_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    __table_args__ = (
        Index("idx_test_set", "test_set_id"),
        Index("idx_test_case", "test_case_id"),
    )


class TestRun(Base):
    __tablename__ = "test_runs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)

    overall_precision: Mapped[float | None] = mapped_column(DECIMAL(5, 4))
    overall_recall: Mapped[float | None] = mapped_column(DECIMAL(5, 4))
    overall_f1: Mapped[float | None] = mapped_column(DECIMAL(5, 4))
    overall_mrr: Mapped[float | None] = mapped_column(DECIMAL(5, 4))
    overall_ndcg: Mapped[float | None] = mapped_column(DECIMAL(5, 4))
    total_test_cases: Mapped[int] = mapped_column(Integer, nullable=False)
    passed_test_cases: Mapped[int] = mapped_column(Integer, nullable=False)

    test_set_ids: Mapped[list[str] | None] = mapped_column(
        JSON, nullable=False, default=list
    )
    custom_case_ids: Mapped[list[str] | None] = mapped_column(
        JSON, nullable=True, default=list
    )

    report_export_format: Mapped[ReportExportFormat | None] = mapped_column(
        Enum(ReportExportFormat, values_callable=lambda obj: [e.value for e in obj]),
        default=ReportExportFormat.MARKDOWN,
    )
    report_storage_path: Mapped[str | None] = mapped_column(String(512))

    status: Mapped[TestRunStatus] = mapped_column(
        Enum(TestRunStatus, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), index=True
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_by: Mapped[int | None] = mapped_column(
        Integer, comment="创建人用户ID，弱关联无需外键"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    snapshot_id: Mapped[str | None] = mapped_column(String(64))
    config_version_id: Mapped[str | None] = mapped_column(String(64), index=True)
    config_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    previous_config_version_id: Mapped[str | None] = mapped_column(String(64))


class TestRunResult(Base):
    __tablename__ = "test_run_results"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("test_runs.id", ondelete="CASCADE"), nullable=False
    )
    test_case_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    query: Mapped[str] = mapped_column(Text, nullable=False)

    precision: Mapped[float | None] = mapped_column(DECIMAL(5, 4))
    recall: Mapped[float | None] = mapped_column(DECIMAL(5, 4))
    f1: Mapped[float | None] = mapped_column(DECIMAL(5, 4))
    mrr: Mapped[float | None] = mapped_column(
        DECIMAL(10, 4), nullable=False, default=0.0
    )
    ndcg: Mapped[float | None] = mapped_column(
        DECIMAL(10, 4), nullable=True, default=None
    )
    hit_rate_1: Mapped[float | None] = mapped_column(
        DECIMAL(10, 4), nullable=False, default=0.0
    )
    hit_rate_3: Mapped[float | None] = mapped_column(
        DECIMAL(10, 4), nullable=False, default=0.0
    )
    hit_rate_5: Mapped[float | None] = mapped_column(
        DECIMAL(10, 4), nullable=False, default=0.0
    )
    passed: Mapped[bool | None] = mapped_column(index=True)
    matched_count: Mapped[int] = mapped_column(Integer, default=0, index=True)
    expected_count: Mapped[int] = mapped_column(Integer, default=0)
    actual_count: Mapped[int] = mapped_column(Integer, default=0)

    expected_knowledge_ids: Mapped[list[str] | None] = mapped_column(JSON)
    actual_knowledge_ids: Mapped[list[str] | None] = mapped_column(JSON)
    retrieved_doc_ids: Mapped[list[str] | None] = mapped_column(
        JSON, nullable=False, default=list
    )
    relevant_doc_ids: Mapped[list[str] | None] = mapped_column(
        JSON, nullable=False, default=list
    )

    error_message: Mapped[str | None] = mapped_column(Text)
    execution_time_ms: Mapped[int | None] = mapped_column(Integer, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (Index("idx_run_id", "run_id"),)
