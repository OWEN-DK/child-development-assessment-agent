"""MD 元数据 ORM — 对标项目已有的 PromptMetadata。

放置位置: backend/src/models/md_metadata.py
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import Column, String, Integer, DateTime, Text

from src.core.database import Base


class MDMetadata(Base):
    """MD 元数据 — 一本书的策管状态。

    对标: PromptMetadata (backend/src/models/prompt_metadata.py)
    """
    __tablename__ = "md_metadata"

    id = Column(String(36), primary_key=True)
    book_id = Column(String(64), nullable=False, unique=True, index=True)
    book_title = Column(String(256), nullable=False)
    author = Column(String(200), nullable=True, comment="作者")
    current_version_id = Column(String(36), nullable=True)  # → MDVersion.id
    version = Column(Integer, default=1, comment="当前版本号")
    status = Column(String(16), default="draft")  # draft / reviewed / published / generating / failed
    file_hash = Column(String(64), nullable=True, comment="源文件哈希值")
    bind_source = Column(String(32), default="kb_bind", comment="来源: kb_bind=从知识库绑定, direct=直接上传")
    total_entities = Column(Integer, default=0)
    total_claims = Column(Integer, default=0)
    total_prescriptions = Column(Integer, default=0)
    total_communities = Column(Integer, default=0, comment="社区数")
    neo4j_synced = Column(Integer, default=0)  # 0=未同步, 1=已同步
    reviewed_by = Column(String(64), nullable=True, comment="审核者")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f"<MDMetadata book_id={self.book_id} status={self.status} v={self.current_version_id}>"
