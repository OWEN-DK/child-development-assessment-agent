"""用户数据模型"""
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, String
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class User(Base):
    """用户表"""
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, comment="用户ID (UUID)")
    tenant_id = Column(String(36), index=True, comment="租户ID（NULL=超管）")
    username = Column(String(100), nullable=False, comment="用户名")
    email = Column(String(255), nullable=False, comment="邮箱")
    password_hash = Column(String(255), nullable=False, comment="密码哈希")
    status = Column(String(20), nullable=False, default="active", comment="状态")
    deleted_at = Column(DateTime, comment="软删除时间")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class UserRole(Base):
    """用户角色关联表"""
    __tablename__ = "user_roles"

    user_id = Column(String(36), primary_key=True, comment="用户ID")
    role_id = Column(String(36), primary_key=True, comment="角色ID")
