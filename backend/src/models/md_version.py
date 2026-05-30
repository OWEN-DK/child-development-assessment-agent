"""MD 版本 ORM — 对标项目已有的 PromptVersion。

放置位置: backend/src/models/md_version.py
"""

from __future__ import annotations

from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, DateTime, Text, JSON

from src.core.database import Base


class MDVersion(Base):
    """MD 版本历史 — 支持回溯和增量更新。

    对标: PromptVersion (backend/src/models/prompt_version.py)
    """
    __tablename__ = "md_version"

    id = Column(String(36), primary_key=True)
    book_id = Column(String(64), nullable=False, index=True)
    version = Column(Integer, nullable=False)
    md_content = Column(Text, nullable=False)        # 完整 MD 内容
    cypher_count = Column(Integer, default=0)         # 生成的 Cypher 语句数
    diff_summary = Column(JSON, nullable=True)        # {added: N, modified: N, deleted: N}
    status = Column(String(16), default="draft")      # draft / reviewed / published
    reviewed_by = Column(String(64), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    published_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f"<MDVersion book_id={self.book_id} v={self.version} status={self.status}>"
