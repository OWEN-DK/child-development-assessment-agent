"""知识库分块数据模型"""
from sqlalchemy import JSON, Column, Integer, MEDIUMTEXT, String
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class KbChunk(Base):
    """知识库分块表"""
    __tablename__ = "kb_chunks"

    id = Column(String(24), primary_key=True, comment="分块ID（雪花ID）")
    kb_id = Column(String(24), nullable=False, index=True, comment="知识库ID")
    doc_id = Column(String(24), nullable=False, index=True, comment="文档ID")
    tenant_id = Column(String(64), nullable=False, index=True, comment="租户ID")
    chunk_index = Column(Integer, nullable=False, comment="分块序号")
    content = Column(MEDIUMTEXT, nullable=False, comment="分块内容")
    token_count = Column(Integer, comment="Token 数量")
    metadata = Column(JSON, comment="分块元数据")
    vector_id = Column(String(100), comment="向量存储中的 ID")
