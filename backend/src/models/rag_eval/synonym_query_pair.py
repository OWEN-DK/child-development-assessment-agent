import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime
from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database import Base
from src.models.rag_eval.enums import RagEvalSynonymSource


class RagEvalSynonymQueryPair(Base):
    __tablename__ = "rag_eval_synonym_query_pairs"
    __table_args__ = (
        Index("idx_rag_eval_synonym_domain_active", "domain", "active"),
        {"comment": "同义查询对表"},
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )

    query_a: Mapped[str] = mapped_column(Text, nullable=False)
    query_b: Mapped[str] = mapped_column(Text, nullable=False)
    domain: Mapped[str] = mapped_column(String(36), nullable=False, comment="发展领域")

    created_by: Mapped[str | None] = mapped_column(String(36), comment="创建者")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    source: Mapped[RagEvalSynonymSource] = mapped_column(
        SAEnum(
            RagEvalSynonymSource, values_callable=lambda obj: [e.value for e in obj]
        ),
        nullable=False,
    )
    active: Mapped[bool] = mapped_column(Boolean, default=True, comment="是否启用")
