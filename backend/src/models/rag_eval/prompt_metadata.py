"""提示词元数据模型 - Phase 7"""

import uuid
from datetime import datetime

from sqlalchemy import (
    String,
    Text,
    DateTime,
    Boolean,
    JSON,
    Enum as SAEnum,
    func,
    Index,
)
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.models.rag_eval.enums import RagEvalPromptCategory


class RagEvalPromptMetadata(Base):
    """提示词元数据 - 提示词级别的静态信息（一个 prompt_key 只有一份）"""

    __tablename__ = "rag_eval_prompt_metadata"
    __table_args__ = (
        Index("idx_rag_eval_prompt_key", "prompt_key", unique=True),
        Index("idx_rag_eval_prompt_category_active", "category", "is_active"),
        {"comment": "RAG评估提示词元数据表"},
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    prompt_key: Mapped[str] = mapped_column(
        String(255), nullable=False, unique=True, comment="提示词唯一标识"
    )
    name_zh: Mapped[str] = mapped_column(
        String(255), nullable=False, comment="中文名称"
    )
    purpose: Mapped[str] = mapped_column(Text, nullable=False, comment="用途说明")
    category: Mapped[RagEvalPromptCategory] = mapped_column(
        SAEnum(
            RagEvalPromptCategory, values_callable=lambda obj: [e.value for e in obj]
        ),
        nullable=False,
        comment="分类",
    )
    subcategory: Mapped[str | None] = mapped_column(String(64), comment="子分类")
    variables_schema: Mapped[dict | None] = mapped_column(
        JSON, comment="变量声明 schema"
    )
    code_references: Mapped[dict | None] = mapped_column(JSON, comment="代码引用位置")
    config_dependencies: Mapped[dict | None] = mapped_column(
        JSON, comment="配置参数依赖"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, comment="是否启用"
    )
    is_system: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, comment="是否系统内置"
    )
    created_by: Mapped[str | None] = mapped_column(String(64), comment="创建人")
    updated_by: Mapped[str | None] = mapped_column(String(64), comment="更新人")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), comment="创建时间"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间"
    )
