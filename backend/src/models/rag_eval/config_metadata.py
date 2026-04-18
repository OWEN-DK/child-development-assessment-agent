"""配置元数据模型 - Phase 8"""

import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import JSON, Boolean, DateTime
from sqlalchemy import Enum as SAEnum
from sqlalchemy import Float, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base


class ConfigCategory(str, Enum):
    """配置分类"""

    RAG_RETRIEVAL = "rag_retrieval"
    RAG_CHUNKING = "rag_chunking"
    LLM = "llm"
    DATABASE = "database"
    REDIS = "redis"
    LOGGING = "logging"
    BUSINESS_RULE = "business_rule"


class ConfigValueType(str, Enum):
    """配置值类型"""

    STRING = "string"
    NUMBER = "number"
    BOOLEAN = "boolean"
    JSON = "json"


class ConfigReloadType(str, Enum):
    """配置重载类型"""

    HOT = "hot"
    COLD = "cold"


class RagEvalConfigMetadata(Base):
    """配置元数据 - 配置项的中文说明、取值范围等"""

    __tablename__ = "rag_eval_config_metadata"
    __table_args__ = (
        Index("idx_rag_eval_config_key", "config_key", unique=True),
        Index("idx_rag_eval_config_category", "category"),
        {"comment": "RAG评估配置元数据表"},
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    config_key: Mapped[str] = mapped_column(
        String(255), nullable=False, unique=True, comment="配置项唯一标识"
    )
    name_zh: Mapped[str] = mapped_column(
        String(255), nullable=False, comment="中文名称"
    )
    description_zh: Mapped[str] = mapped_column(
        Text, nullable=False, comment="中文说明"
    )
    category: Mapped[ConfigCategory] = mapped_column(
        SAEnum(ConfigCategory, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        comment="分类",
    )
    value_type: Mapped[ConfigValueType] = mapped_column(
        SAEnum(ConfigValueType, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        comment="值类型",
    )
    min_value: Mapped[float | None] = mapped_column(Float, comment="最小值")
    max_value: Mapped[float | None] = mapped_column(Float, comment="最大值")
    recommended_min: Mapped[float | None] = mapped_column(Float, comment="推荐最小值")
    recommended_max: Mapped[float | None] = mapped_column(Float, comment="推荐最大值")
    unit: Mapped[str | None] = mapped_column(String(32), comment="单位")
    affected_components: Mapped[dict | None] = mapped_column(
        JSON, comment="影响组件列表"
    )
    reload_type: Mapped[ConfigReloadType] = mapped_column(
        SAEnum(ConfigReloadType, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        default=ConfigReloadType.HOT,
        comment="重载方式",
    )
    is_system: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, comment="是否系统内置"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), comment="创建时间"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间"
    )
