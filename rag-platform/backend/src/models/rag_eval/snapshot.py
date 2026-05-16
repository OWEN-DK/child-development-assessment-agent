"""知识库快照模型"""
from datetime import datetime

from sqlalchemy import JSON, Column, DateTime, Integer, String

from src.models.base import Base


class KnowledgeSnapshot(Base):
    """知识库快照表"""
    __tablename__ = "knowledge_snapshots"

    id = Column(String(64), primary_key=True, comment="快照ID")
    kb_id = Column(String(24), nullable=False, index=True, comment="知识库ID")
    tenant_id = Column(String(64), nullable=False, index=True, comment="租户ID")
    name = Column(String(255), comment="快照名称")
    vector_store_path = Column(String(500))
    vector_backend_type = Column(String(20))
    document_count = Column(Integer, default=0)
    chunk_count = Column(Integer, default=0)
    doc_ids_json = Column(JSON, comment="文档ID列表")
    chunk_strategy_json = Column(JSON)
    embedding_config_json = Column(JSON)
    config_snapshot = Column(JSON)
    status = Column(String(20), default="active", comment="状态：active/invalid/expired")
    expires_at = Column(DateTime)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
