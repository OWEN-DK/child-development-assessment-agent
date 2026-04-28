from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base


class KnowledgeSnapshot(Base):
    __tablename__ = "knowledge_snapshots"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    vector_store_path: Mapped[str] = mapped_column(
        String(512), nullable=False, comment="向量库存储路径"
    )
    document_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    chunk_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    config_version_id: Mapped[str | None] = mapped_column(
        String(64), index=True, comment="配置版本 ID"
    )
    config_snapshot: Mapped[dict[str, Any] | None] = mapped_column(
        JSON, comment="配置快照 JSON"
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = {"extend_existing": True}
