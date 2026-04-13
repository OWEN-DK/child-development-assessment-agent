from sqlalchemy import String, Text, DateTime, Enum, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.core.database import Base
from datetime import datetime
from enum import Enum as PyEnum
from typing import Any, Optional


class ConfigAction(PyEnum):
    UPDATE = "UPDATE"
    ROLLBACK = "ROLLBACK"
    RESET = "RESET"


class ConfigVersion(Base):
    __tablename__ = "config_versions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, index=True
    )
    created_by: Mapped[str | None] = mapped_column(String(64))
    description: Mapped[str | None] = mapped_column(Text)
    config_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON)
    parent_version_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("config_versions.id")
    )
    is_factory_reset: Mapped[bool] = mapped_column(default=False)

    parent_version: Mapped["ConfigVersion | None"] = relationship(remote_side=[id])


class ConfigAuditLog(Base):
    __tablename__ = "config_audit_log"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, index=True
    )
    action: Mapped[ConfigAction] = mapped_column(
        Enum(ConfigAction, values_callable=lambda obj: [e.value for e in obj]),
        index=True,
    )
    from_version: Mapped[str | None] = mapped_column(String(64), index=True)
    to_version: Mapped[str | None] = mapped_column(String(64), index=True)
    user: Mapped[str | None] = mapped_column(String(64))
