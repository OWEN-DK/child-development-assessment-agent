import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime
from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database import Base
from src.models.rag_eval.enums import RagEvalChangeSetStatus


class RagEvalConfigChangeSet(Base):
    __tablename__ = "rag_eval_config_change_sets"
    __table_args__ = (
        Index("idx_rag_eval_config_change_set_status", "status"),
        Index("idx_rag_eval_config_change_set_config_version", "config_version_id"),
        {"comment": "配置变更集表"},
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )

    change_set_label: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="展示用标签，格式 CS-20260416-001"
    )
    config_version_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("rag_eval_config_versions.id", ondelete="SET NULL"),
        comment="发布后生成的配置版本ID",
    )

    status: Mapped[RagEvalChangeSetStatus] = mapped_column(
        SAEnum(
            RagEvalChangeSetStatus, values_callable=lambda obj: [e.value for e in obj]
        ),
        nullable=False,
        default=RagEvalChangeSetStatus.COMMITTED,
    )
    rollback_reason: Mapped[str | None] = mapped_column(String(500), comment="回滚原因")

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    config_version: Mapped["RagEvalConfigVersion | None"] = relationship(
        back_populates="change_sets"
    )
    prompt_changes: Mapped[list["RagEvalConfigChangeSetPrompt"]] = relationship(
        back_populates="change_set", cascade="all, delete-orphan"
    )
