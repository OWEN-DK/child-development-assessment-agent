"""提示词元数据模型

提示词级别的静态信息（一个 prompt_key 只有一份）。
"""

import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime
from sqlalchemy import Enum as SAEnum
from sqlalchemy import Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.models.prompt_enums import PromptCategory


class PromptMetadata(Base):
    """提示词元数据 - 提示词级别的静态信息（一个 prompt_key 只有一份）"""

    __tablename__ = "prompt_metadata"
    __table_args__ = (
        Index("idx_prompt_key", "prompt_key", unique=True),
        Index("idx_prompt_category_active", "category", "is_active"),
        {"comment": "提示词元数据表"},
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
    category: Mapped[PromptCategory] = mapped_column(
        SAEnum(
            PromptCategory, values_callable=lambda obj: [e.value for e in obj]
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
