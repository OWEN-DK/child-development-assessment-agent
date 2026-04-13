from sqlalchemy import (
    String,
    Text,
    DECIMAL,
    Enum,
    Integer,
    JSON,
    DateTime,
    ForeignKey,
    func,
    Index,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.core.database import Base
from datetime import datetime
from enum import Enum as PyEnum
from typing import Any, List, Tuple, Optional
from pydantic import BaseModel


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


class GenerationParams(BaseModel):
    target_domains: List[str]
    age_range: Tuple[float, float]
    count: int = 10
    difficulty: str = "medium"
    llm_model: str = "qwen-plus"
    temperature: float = 0.7


class DocumentStatus(PyEnum):
    UPLOADED = "uploaded"
    PARSING = "parsing"
    READY = "ready"
    ARCHIVED = "archived"


class TestResultItem(BaseModel):
    test_case_id: str
    passed: bool
    precision: float
    recall: float
    f1: float
    execution_time_ms: int
    expected_knowledge_ids: List[str]
    actual_knowledge_ids: List[str]
    error_message: Optional[str] = None


class SourceDocument(Base):
    __tablename__ = "source_documents"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    file_type: Mapped[str] = mapped_column(String(10), nullable=False)
    file_path: Mapped[str] = mapped_column(String(512), nullable=False)
    file_hash: Mapped[str] = mapped_column(String(64), index=True)
    content_summary: Mapped[str | None] = mapped_column(Text)
    page_count: Mapped[int | None] = mapped_column(Integer)
    chapter_structure: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    quality_report: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    status: Mapped[DocumentStatus] = mapped_column(
        Enum(DocumentStatus, values_callable=lambda obj: [e.value for e in obj]),
        default=DocumentStatus.UPLOADED,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


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
    source_document_id: Mapped[str] = mapped_column(String(64), nullable=False)
    query: Mapped[str] = mapped_column(Text, nullable=False)
    age: Mapped[float] = mapped_column(DECIMAL(4, 1), nullable=False)
    domain: Mapped[TestDomain] = mapped_column(
        Enum(TestDomain, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
    )
    description: Mapped[str | None] = mapped_column(Text)

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

    status: Mapped[TestRunStatus] = mapped_column(
        Enum(TestRunStatus, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), index=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)

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
    passed: Mapped[bool | None] = mapped_column(index=True)
    matched_count: Mapped[int] = mapped_column(Integer, default=0, index=True)
    expected_count: Mapped[int] = mapped_column(Integer, default=0)
    actual_count: Mapped[int] = mapped_column(Integer, default=0)

    expected_knowledge_ids: Mapped[list[str] | None] = mapped_column(JSON)
    actual_knowledge_ids: Mapped[list[str] | None] = mapped_column(JSON)

    error_message: Mapped[str | None] = mapped_column(Text)
    execution_time_ms: Mapped[int | None] = mapped_column(Integer, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (Index("idx_run_id", "run_id"),)
