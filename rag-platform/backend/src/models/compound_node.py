"""复合节点数据模型"""
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text

from src.models.base import Base


class CompoundNode(Base):
    """复合节点表"""
    __tablename__ = "compound_nodes"

    id = Column(String(64), primary_key=True, comment="复合节点ID (UUID)")
    tenant_id = Column(String(64), nullable=False, index=True, comment="租户ID")
    owner_id = Column(String(64), nullable=False, index=True, comment="创建者用户ID")
    name = Column(String(255), nullable=False, comment="复合节点名称")
    description = Column(Text, comment="描述")
    config_snapshot = Column(Text, nullable=False, comment="配置 JSON")
    is_shared = Column(Boolean, nullable=False, default=False, comment="是否共享")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
