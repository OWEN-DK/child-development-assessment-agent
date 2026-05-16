"""发布端点数据模型"""
from datetime import datetime

from sqlalchemy import JSON, BigInteger, Boolean, Column, DateTime, Integer, String, Text

from src.models.base import Base


class PublishedEndpoint(Base):
    """发布端点表

    管道对外暴露的搜索 URL，支持 JWT/API Key 认证和速率限制。
    """
    __tablename__ = "published_endpoints"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="自增主键")
    endpoint_id = Column(String(64), nullable=False, unique=True, comment="端点ID (UUID)")
    pipeline_id = Column(String(64), nullable=False, index=True, comment="管道ID")
    tenant_id = Column(String(64), nullable=False, index=True, comment="租户ID")
    url_path = Column(String(200), nullable=False, unique=True, comment="URL 路径（全局唯一）")
    bound_version = Column(Integer, nullable=False, comment="绑定的管道版本")
    http_method = Column(String(10), nullable=False, default="POST", comment="HTTP 方法")
    auth_type = Column(String(20), nullable=False, default="jwt", comment="认证类型：jwt/api_key/none")
    rate_limit = Column(Integer, nullable=False, default=0, comment="QPS 限制（0=不限）")
    enabled = Column(Boolean, nullable=False, default=True, comment="是否启用")
    allowed_params = Column(JSON, comment="允许的 API 参数白名单")
    response_format = Column(String(20), nullable=False, default="json", comment="响应格式：json/sse/custom")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
