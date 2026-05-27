"""知识图谱数据模型 — LazyGraphRAG 存储层

三张核心表:
  - GraphEntity: 领域实体（7 种类型）
  - GraphRelation: 实体间关系（6 种类型）
  - GraphCommunityNode: Louvain 层级社区树节点
"""

from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import (JSON, Boolean, DateTime, Enum, Float, Index, Integer,
                        String, Text, func)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base


class EntityType(PyEnum):
    DEVELOPMENT_CONCEPT = "development_concept"
    SYMPTOM_BEHAVIOR = "symptom_behavior"
    INTERVENTION_METHOD = "intervention_method"
    ASSESSMENT_TOOL = "assessment_tool"
    BRAIN_REGION = "brain_region"
    AGE_MILESTONE = "age_milestone"
    CLINICAL_POPULATION = "clinical_population"


class RelationType(PyEnum):
    CAUSES = "causes"
    TREATS = "treats"
    ASSESSES = "assesses"
    RELATED_TO = "related_to"
    CONTRAINDICATES = "contraindicates"
    DEVELOPS_AT = "develops_at"


class CommunityScope(PyEnum):
    BOOK = "book"
    GLOBAL = "global"


class GraphEntity(Base):
    __tablename__ = "graph_entities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, comment="实体名称")
    entity_type: Mapped[EntityType] = mapped_column(
        Enum(EntityType, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        comment="实体类型",
    )
    description: Mapped[str | None] = mapped_column(Text, comment="实体描述")
    aliases: Mapped[dict | None] = mapped_column(JSON, comment="别名列表")
    book_id: Mapped[str] = mapped_column(String(64), nullable=False, comment="所属书籍ID(UUID)")
    chunk_ids: Mapped[dict | None] = mapped_column(JSON, comment="关联块ID列表")
    embedding: Mapped[dict | None] = mapped_column(JSON, comment="跨书实体去重用 embedding")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp(), comment="创建时间"
    )

    __table_args__ = (
        Index("idx_graph_entity_book", "book_id"),
        Index("idx_graph_entity_type", "entity_type"),
    )


class GraphRelation(Base):
    __tablename__ = "graph_relations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_entity_id: Mapped[int] = mapped_column(Integer, nullable=False, comment="源实体ID")
    target_entity_id: Mapped[int] = mapped_column(Integer, nullable=False, comment="目标实体ID")
    relation_type: Mapped[RelationType] = mapped_column(
        Enum(RelationType, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        comment="关系类型",
    )
    description: Mapped[str | None] = mapped_column(Text, comment="关系描述")
    confidence: Mapped[float] = mapped_column(Float, default=1.0, comment="置信度")
    book_id: Mapped[str] = mapped_column(String(64), nullable=False, comment="所属书籍ID(UUID)")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp(), comment="创建时间"
    )

    __table_args__ = (
        Index("idx_graph_rel_source", "source_entity_id"),
        Index("idx_graph_rel_target", "target_entity_id"),
        Index("idx_graph_rel_type", "relation_type"),
    )


class GraphCommunityNode(Base):
    __tablename__ = "graph_community_tree"

    node_id: Mapped[str] = mapped_column(String(64), primary_key=True, comment="社区节点ID")
    parent_id: Mapped[str | None] = mapped_column(String(64), comment="父节点ID")
    level: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="层级深度")
    scope: Mapped[CommunityScope] = mapped_column(
        Enum(CommunityScope, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        default=CommunityScope.BOOK,
        comment="作用域",
    )
    book_id: Mapped[str | None] = mapped_column(String(64), comment="scope=book 时非空(UUID)")
    label: Mapped[str | None] = mapped_column(String(500), comment="社区标签")
    entity_names: Mapped[dict | None] = mapped_column(JSON, comment="社区内实体名列表")
    chunk_ids: Mapped[dict | None] = mapped_column(JSON, comment="叶子节点关联块ID")
    is_leaf: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, comment="是否叶子")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp(), comment="创建时间"
    )

    __table_args__ = (
        Index("idx_comm_parent", "parent_id"),
        Index("idx_comm_scope_level", "scope", "level"),
    )
