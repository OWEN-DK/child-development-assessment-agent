import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database import Base


class RagEvalConfigChangeSetPrompt(Base):
    __tablename__ = "rag_eval_config_change_set_prompts"
    __table_args__ = (
        Index(
            "uk_rag_eval_change_set_prompt",
            "change_set_id",
            "prompt_version_id",
            unique=True,
        ),
        Index("idx_rag_eval_change_set_prompt_version", "prompt_version_id"),
        {"comment": "变更集-提示词版本关联表"},
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )

    change_set_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("rag_eval_config_change_sets.id", ondelete="CASCADE"),
        nullable=False,
    )
    prompt_version_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("rag_eval_prompt_versions.id", ondelete="CASCADE"),
        nullable=False,
    )

    change_set: Mapped["RagEvalConfigChangeSet"] = relationship(
        back_populates="prompt_changes"
    )
    prompt_version: Mapped["RagEvalPromptVersion"] = relationship(
        back_populates="change_set_prompts"
    )
