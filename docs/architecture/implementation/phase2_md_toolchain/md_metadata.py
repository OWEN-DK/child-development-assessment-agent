"""MD 元数据 ORM — 对标项目已有的 PromptMetadata。

放置位置: backend/src/models/md_metadata.py
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import Column, String, Integer, DateTime, Text
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class MDMetadata(Base):
    """MD 元数据 — 一本书的策管状态。

    对标: PromptMetadata (backend/src/models/prompt_metadata.py)
    """
    __tablename__ = "md_metadata"

    id = Column(String(36), primary_key=True)
    book_id = Column(String(64), nullable=False, unique=True, index=True)
    book_title = Column(String(256), nullable=False)
    current_version_id = Column(String(36), nullable=True)  # → MDVersion.id
    status = Column(String(16), default="draft")  # draft / reviewed / published
    total_entities = Column(Integer, default=0)
    total_claims = Column(Integer, default=0)
    total_prescriptions = Column(Integer, default=0)
    neo4j_synced = Column(Integer, default=0)  # 0=未同步, 1=已同步
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f"<MDMetadata book_id={self.book_id} status={self.status} v={self.current_version_id}>"
