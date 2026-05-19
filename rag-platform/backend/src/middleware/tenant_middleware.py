"""租户上下文中间件

从 JWT token 解析 tenant_id 并注入请求上下文。
配合 core/auth/tenant_context.py 使用。
"""
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from src.core.auth.tenant_context import TenantContext, clear_current_context, set_current_context
from src.utils.logger import logger


class TenantMiddleware(BaseHTTPMiddleware):
    """租户上下文注入中间件"""

    async def dispatch(self, request: Request, call_next):
        tenant_id = getattr(request.state, "tenant_id", None)
        user_id = getattr(request.state, "user_id", None)
        roles = getattr(request.state, "roles", [])

        ctx = TenantContext(
            tenant_id=tenant_id,
            user_id=user_id,
            roles=roles,
        )
        set_current_context(ctx)
        try:
            return await call_next(request)
        finally:
            clear_current_context()
