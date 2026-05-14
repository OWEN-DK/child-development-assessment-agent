"""知识库数据模型"""
from datetime import datetime

from sqlalchemy import JSON, BigInteger, Column, DateTime, Integer, String
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class KnowledgeBase(Base):
    """知识库表"""
    __tablename__ = "knowledge_bases"

    id = Column(String(24), primary_key=True, comment="知识库ID（雪花ID）")
    tenant_id = Column(String(64), nullable=False, index=True, comment="租户ID")
    name = Column(String(255), nullable=False, comment="知识库名称")
    description = Column(String(500), comment="描述")
    vector_backend = Column(String(20), nullable=False, default="chroma", comment="向量后端：chroma/es/milvus")
    chunk_strategy = Column(JSON, comment="分块策略配置")
    embedding_config = Column(JSON, comment="Embedding 配置")
    visibility = Column(String(20), nullable=False, default="public", comment="可见性：public/role_scoped/private")
    visible_roles = Column(JSON, comment="可见角色列表（role_scoped 时生效）")
    owner_id = Column(String(64), nullable=False, comment="创建者ID")
    status = Column(String(20), nullable=False, default="ready", comment="状态：ready/rebuilding/indexing/error")
    document_count = Column(Integer, nullable=False, default=0, comment="文档数量")
    chunk_count = Column(Integer, nullable=False, default=0, comment="分块数量")
    storage_size_bytes = Column(BigInteger, nullable=False, default=0, comment="存储大小（字节）")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
