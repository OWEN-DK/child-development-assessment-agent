import uuid
from datetime import datetime

from sqlalchemy import (JSON, DateTime, ForeignKey, Index, Integer, String,
                        Text, func)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database import Base


class RagEvalPromptVersion(Base):
    __tablename__ = "rag_eval_prompt_versions"
    __table_args__ = (
        Index(
            "idx_rag_eval_prompt_key_version",
            "prompt_key",
            "version_label",
            unique=True,
        ),
        Index("idx_rag_eval_prompt_key_created", "prompt_key", "created_at"),
        {"comment": "提示词版本表"},
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )

    prompt_key: Mapped[str] = mapped_column(
        String(255), nullable=False, comment="如 query_rewrite, query_routing"
    )
    version_label: Mapped[str] = mapped_column(
        String(36), nullable=False, comment="展示用版本号，如 v3, v4-new-constraint"
    )
    version_number: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="该prompt_key下的自增序号，仅用于排序"
    )
    content: Mapped[str] = mapped_column(Text, nullable=False, comment="提示词完整内容")
    variables_extracted: Mapped[list | None] = mapped_column(
        JSON, comment="自动从content中提取的变量列表"
    )
    change_impact: Mapped[dict | None] = mapped_column(JSON, comment="变更影响分析")

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    created_by: Mapped[str | None] = mapped_column(String(36), comment="创建人用户ID")
    change_summary: Mapped[str | None] = mapped_column(Text, comment="变更摘要")

    change_set_prompts: Mapped[list["RagEvalConfigChangeSetPrompt"]] = relationship(
        back_populates="prompt_version"
    )
    prompt_suggestions_current: Mapped[list["RagEvalPromptSuggestionRecord"]] = (
        relationship(
            back_populates="current_prompt_version",
            foreign_keys="RagEvalPromptSuggestionRecord.current_version_id",
        )
    )
    prompt_suggestions_suggested: Mapped[list["RagEvalPromptSuggestionRecord"]] = (
        relationship(
            back_populates="suggested_prompt_version",
            foreign_keys="RagEvalPromptSuggestionRecord.suggested_version_id",
        )
    )
