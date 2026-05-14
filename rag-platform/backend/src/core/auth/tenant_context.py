"""租户上下文管理

基于 contextvars 实现异步安全的请求上下文传播。
从 request.state 提取 tenant_id/user_id/roles/is_superadmin，
构造 TenantContext 对象供下游服务使用。
"""
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class TenantContext:
    """租户上下文"""
    tenant_id: Optional[str] = None
    user_id: Optional[str] = None
    roles: list[str] = field(default_factory=list)
    is_superadmin: bool = False
    is_god_mode: bool = False

    @property
    def is_authenticated(self) -> bool:
        """是否已认证"""
        return self.user_id is not None

    @property
    def is_tenant_user(self) -> bool:
        """是否租户用户"""
        return self.tenant_id is not None and not self.is_superadmin


# 请求级上下文变量（异步安全）
_current_context: ContextVar[Optional[TenantContext]] = ContextVar(
    "tenant_context", default=None
)


def get_current_context() -> Optional[TenantContext]:
    """获取当前请求的租户上下文"""
    return _current_context.get()


def set_current_context(context: TenantContext) -> None:
    """设置当前请求的租户上下文"""
    _current_context.set(context)


def clear_current_context() -> None:
    """清除当前请求的租户上下文"""
    _current_context.set(None)


def require_tenant_id() -> str:
    """获取当前租户 ID（必须存在）

    Raises:
        RuntimeError: 无租户上下文
    """
    ctx = get_current_context()
    if ctx is None or ctx.tenant_id is None:
        raise RuntimeError("缺少租户上下文，请确保请求经过认证中间件")
    return ctx.tenant_id


def require_user_id() -> str:
    """获取当前用户 ID（必须存在）

    Raises:
        RuntimeError: 无用户上下文
    """
    ctx = get_current_context()
    if ctx is None or ctx.user_id is None:
        raise RuntimeError("缺少用户上下文，请确保请求经过认证中间件")
    return ctx.user_id
