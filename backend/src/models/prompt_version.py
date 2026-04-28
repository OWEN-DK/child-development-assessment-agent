"""提示词版本模型

存储提示词的完整版本历史（一个 prompt_key 多条记录）。
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, DateTime, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base


class PromptVersion(Base):
    """提示词版本 - 存储提示词的完整版本历史"""

    __tablename__ = "prompt_versions"
    __table_args__ = (
        Index("idx_prompt_key_version", "prompt_key", "version_label", unique=True),
        Index("idx_prompt_key_created", "prompt_key", "created_at"),
        Index("idx_prompt_key_version_number", "prompt_key", "version_number"),
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
        Integer, nullable=False, comment="该 prompt_key 下的自增序号，仅用于排序"
    )
    content: Mapped[str] = mapped_column(Text, nullable=False, comment="提示词完整内容")
    content_hash: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True, comment="内容 SHA256 哈希"
    )
    variables_extracted: Mapped[list | None] = mapped_column(
        JSON, comment="自动从 content 中提取的变量列表"
    )
    change_impact: Mapped[dict | None] = mapped_column(JSON, comment="变更影响分析")
    change_summary: Mapped[str | None] = mapped_column(Text, comment="变更摘要")
    tags: Mapped[list | None] = mapped_column(JSON, comment="标签列表")
    fallback: Mapped[str | None] = mapped_column(Text, comment="降级备用内容")

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    created_by: Mapped[str | None] = mapped_column(String(36), comment="创建人用户 ID")
