"""知识库重建任务数据模型"""
from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, SMALLINT, String, Text

from src.models.base import Base


class KbRebuildTask(Base):
    """知识库重建任务表"""
    __tablename__ = "kb_rebuild_tasks"

    id = Column(String(24), primary_key=True, comment="任务ID")
    kb_id = Column(String(24), nullable=False, index=True, comment="知识库ID")
    tenant_id = Column(String(64), nullable=False, index=True, comment="租户ID")
    trigger = Column(String(30), nullable=False, comment="触发原因：chunk_change/embedding_change/backend_migration")
    status = Column(String(20), nullable=False, default="running", index=True, comment="状态：running/completed/failed")
    progress_pct = Column(SMALLINT, nullable=False, default=0, comment="进度百分比")
    progress_message = Column(String(500), comment="进度消息")
    started_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    completed_at = Column(DateTime, comment="完成时间")
    error_message = Column(Text, comment="错误信息")
