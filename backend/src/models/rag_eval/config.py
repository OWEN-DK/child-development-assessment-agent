from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base


class EvalConfigVersion(Base):
    """评估配置版本（独立于系统配置版本）"""

    __tablename__ = "eval_config_versions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    version_number: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, comment="版本序号（应用层维护）"
    )
    version_label: Mapped[str | None] = mapped_column(
        String(100), comment="版本标签"
    )
    config_snapshot: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, comment="完整配置快照"
    )
    change_summary: Mapped[str | None] = mapped_column(Text, comment="变更摘要")
    created_by: Mapped[str | None] = mapped_column(String(64), comment="创建者")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = {"extend_existing": True}


class EvalConfigChangeSet(Base):
    """评估配置变更集"""

    __tablename__ = "eval_config_change_sets"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    change_set_label: Mapped[str] = mapped_column(
        String(255), nullable=False, comment="变更集标签"
    )
    config_version_id: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True, comment="目标配置版本"
    )
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="committed", index=True, comment="committed/rolled_back"
    )
    rollback_reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    rolled_back_at: Mapped[datetime | None] = mapped_column(DateTime)

    __table_args__ = {"extend_existing": True}
