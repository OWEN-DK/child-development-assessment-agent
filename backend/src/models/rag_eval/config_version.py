import uuid
from datetime import datetime

from sqlalchemy import (JSON, DateTime, ForeignKey, Index, Integer, String,
                        Text, func)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database import Base


class RagEvalConfigVersion(Base):
    __tablename__ = "rag_eval_config_versions"
    __table_args__ = (
        Index("idx_rag_eval_config_version_created_at", "created_at"),
        {"comment": "RAG配置版本表"},
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )

    version_number: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="自增序号，系统自动维护"
    )
    version_label: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="展示用语义版本号，如 v2.3"
    )
    config_snapshot: Mapped[dict] = mapped_column(
        JSON, nullable=False, comment="完整配置快照"
    )

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    created_by: Mapped[str | None] = mapped_column(String(36), comment="创建人用户ID")
    change_summary: Mapped[str | None] = mapped_column(Text, comment="变更摘要")

    test_runs: Mapped[list["RagEvalTestRun"]] = relationship(
        back_populates="config_version"
    )
    change_sets: Mapped[list["RagEvalConfigChangeSet"]] = relationship(
        back_populates="config_version"
    )
    reports: Mapped[list["RagEvalTestReport"]] = relationship(
        back_populates="config_version"
    )
