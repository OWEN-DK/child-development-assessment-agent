"""知识问答历史记录模型"""

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Index, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base


class KnowledgeQAHistory(Base):
    """知识问答历史记录

    每次问答保存一条记录，支持按时间倒序查询。
    status: completed / partial / cancelled / timeout / error
    """

    __tablename__ = "knowledge_qa_history"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    task_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="completed",
        comment="completed / partial / cancelled / timeout / error",
    )
    result_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, comment="完整的问答结果")
    matched_books_json: Mapped[list[dict[str, Any]] | None] = mapped_column(
        JSON, nullable=True, comment="匹配到的书籍列表"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), index=True
    )

    __table_args__ = (
        Index("idx_kqa_history_task_id", "task_id"),
        Index("idx_kqa_history_created_at", "created_at"),
        Index("idx_kqa_history_status", "status"),
        {"extend_existing": True},
    )
