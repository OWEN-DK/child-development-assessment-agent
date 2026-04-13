from sqlalchemy import (
    String,
    Text,
    DECIMAL,
    Enum,
    Integer,
    JSON,
    DateTime,
    func,
    Index,
)
from sqlalchemy.orm import Mapped, mapped_column
from src.core.database import Base
from datetime import datetime
from enum import Enum as PyEnum
from typing import Any


class DocumentStatus(PyEnum):
    UPLOADED = "uploaded"
    PARSING = "parsing"
    READY = "ready"
    ARCHIVED = "archived"


class ImportStatus(PyEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    INDEXED = "indexed"
    FAILED = "failed"


class SourceDocument(Base):
    __tablename__ = "source_documents"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    file_type: Mapped[str] = mapped_column(
        Enum("pdf", "epub", "txt"), nullable=False, index=True
    )
    file_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    content_summary: Mapped[str | None] = mapped_column(Text)

    page_count: Mapped[int | None] = mapped_column(Integer)
    chapter_count: Mapped[int | None] = mapped_column(Integer)
    quality_score: Mapped[float | None] = mapped_column(DECIMAL(3, 2), index=True)
    scan_page_ratio: Mapped[float | None] = mapped_column(DECIMAL(3, 2))

    chapter_structure: Mapped[list[str] | None] = mapped_column(JSON)
    quality_report: Mapped[dict[str, Any] | None] = mapped_column(JSON)

    status: Mapped[DocumentStatus] = mapped_column(
        Enum(DocumentStatus, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index("idx_file_hash", "file_hash"),
        Index("idx_status", "status"),
        Index("idx_file_type", "file_type"),
        {"extend_existing": True},
    )


class DocumentRecord(Base):
    __tablename__ = "document_records"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    file_name: Mapped[str] = mapped_column(String(500), nullable=False)
    upload_date: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)

    total_pages: Mapped[int | None] = mapped_column(Integer)
    indexed_chunks: Mapped[int] = mapped_column(Integer, default=0, index=True)
    category: Mapped[str | None] = mapped_column(String(100), index=True)

    ref_doc_ids: Mapped[list[str] | None] = mapped_column(JSON)
    extra_metadata: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSON)

    status: Mapped[ImportStatus] = mapped_column(
        Enum(ImportStatus, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        index=True,
    )
    progress: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = {"extend_existing": True}
