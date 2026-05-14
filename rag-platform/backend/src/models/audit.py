"""审计日志数据模型"""
from datetime import datetime

from sqlalchemy import JSON, Column, DateTime, String, Text
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class GodModeAuditLog(Base):
    """God Mode 审计日志"""
    __tablename__ = "god_mode_audit_log"

    id = Column(String(36), primary_key=True, comment="日志ID")
    tenant_id = Column(String(36), nullable=False, index=True, comment="租户ID")
    actor_id = Column(String(36), nullable=False, index=True, comment="超管ID")
    action = Column(String(50), nullable=False, comment="操作类型")
    target_type = Column(String(50), comment="目标类型")
    target_id = Column(String(64), comment="目标ID")
    details = Column(Text, comment="操作详情")
    session_started_at = Column(DateTime, comment="会话开始时间")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class PermissionAuditLog(Base):
    """权限审计日志"""
    __tablename__ = "permission_audit_log"

    id = Column(String(36), primary_key=True, comment="日志ID")
    tenant_id = Column(String(36), nullable=False, index=True, comment="租户ID")
    actor_id = Column(String(36), nullable=False, comment="操作人ID")
    action = Column(String(50), nullable=False, comment="操作类型")
    target_type = Column(String(50), nullable=False, comment="目标类型")
    target_id = Column(String(64), nullable=False, comment="目标ID")
    old_value = Column(JSON, comment="旧值")
    new_value = Column(JSON, comment="新值")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class TenantAuditLog(Base):
    """租户审计日志"""
    __tablename__ = "tenant_audit_log"

    id = Column(String(36), primary_key=True, comment="日志ID")
    tenant_id = Column(String(36), nullable=False, index=True, comment="租户ID")
    actor_id = Column(String(36), nullable=False, comment="超管ID")
    action = Column(String(50), nullable=False, comment="操作类型")
    details = Column(Text, comment="操作详情")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class TenantDeletionSnapshot(Base):
    """租户删除快照"""
    __tablename__ = "tenant_deletion_snapshots"

    id = Column(String(36), primary_key=True, comment="快照ID")
    tenant_id = Column(String(36), nullable=False, index=True, comment="租户ID")
    snapshot_path = Column(String(500), nullable=False, comment="快照文件路径")
    status = Column(String(20), nullable=False, default="pending", comment="状态")
    expires_at = Column(DateTime, nullable=False, comment="过期时间")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
