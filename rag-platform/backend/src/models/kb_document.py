"""知识库文档数据模型"""
from datetime import datetime

from sqlalchemy import JSON, Column, DateTime, Integer, String
from sqlalchemy.dialects.mysql import MEDIUMTEXT

from src.models.base import Base


class KbDocument(Base):
    """知识库文档表"""
    __tablename__ = "kb_documents"

    id = Column(String(24), primary_key=True, comment="文档ID（雪花ID）")
    kb_id = Column(String(24), nullable=False, index=True, comment="知识库ID")
    tenant_id = Column(String(64), nullable=False, index=True, comment="租户ID")
    filename = Column(String(500), nullable=False, comment="文件名")
    file_type = Column(String(20), nullable=False, comment="文件类型：pdf/txt/markdown/html/epub")
    file_size = Column(Integer, nullable=False, comment="文件大小（字节）")
    page_count = Column(Integer, comment="页数")
    md5_hash = Column(String(32), nullable=False, index=True, comment="文件 MD5")
    parse_status = Column(String(20), nullable=False, default="pending", index=True, comment="解析状态：pending/parsing/parsed/error")
    error_message = Column(String(500), comment="错误信息")
    text_content = Column(MEDIUMTEXT, comment="提取的文本内容")
    doc_metadata = Column("metadata", JSON, comment="文档元数据")
    access_level = Column(String(20), nullable=False, default="inherit", comment="权限级别：inherit/restricted")
    doc_acl = Column(JSON, comment="文档 ACL 角色列表")
    owner_id = Column(String(64), nullable=False, comment="上传者ID")
    chunk_count = Column(Integer, nullable=False, default=0, comment="分块数量")
    uploaded_at = Column(DateTime, nullable=False, default=datetime.utcnow)
