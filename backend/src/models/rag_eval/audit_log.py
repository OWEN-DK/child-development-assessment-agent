"""审计日志模型 - 记录所有配置和提示词变更操作"""

import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base


class RagEvalAuditLog(Base):
    __tablename__ = "rag_eval_audit_logs"
    __table_args__ = (
        Index("idx_rag_eval_audit_log_operator", "operator"),
        Index("idx_rag_eval_audit_log_action", "action"),
        Index("idx_rag_eval_audit_log_target_type", "target_type"),
        Index("idx_rag_eval_audit_log_target_id", "target_id"),
        Index("idx_rag_eval_audit_log_created_at", "created_at"),
        {"comment": "审计日志表"},
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )

    operator: Mapped[str] = mapped_column(String(100), nullable=False, comment="操作人")
    action: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="操作类型: create/update/delete/rollback/apply",
    )
    target_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="目标类型: config/prompt/test_set/test_case",
    )
    target_id: Mapped[str] = mapped_column(
        String(36), nullable=False, comment="目标 ID"
    )

    before_value: Mapped[dict | None] = mapped_column(JSON, comment="变更前值")
    after_value: Mapped[dict] = mapped_column(JSON, comment="变更后值")
    diff_summary: Mapped[str | None] = mapped_column(Text, comment="变更摘要")

    ip_address: Mapped[str | None] = mapped_column(String(45), comment="操作 IP")
    user_agent: Mapped[str | None] = mapped_column(String(500), comment="用户代理")

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), comment="创建时间"
    )
