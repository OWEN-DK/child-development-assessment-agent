"""JWT 认证中间件

从 Authorization: Bearer <token> 提取 token → 验证 → 注入 request.state。
豁免路径：/health, /metrics, /api/v1/auth/login, /api/v1/users/accept-invitation
"""
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from src.core.auth.exceptions import AuthenticationError
from src.core.auth.tenant_context import TenantContext, set_current_context, clear_current_context
from src.utils.logger import logger

# 豁免认证的路径前缀
EXEMPT_PATHS = [
    "/health",
    "/metrics",
    "/api/v1/auth/login",
    "/api/v1/auth/refresh",
    "/api/v1/users/accept-invitation",
    "/docs",
    "/openapi.json",
]


class AuthMiddleware(BaseHTTPMiddleware):
    """JWT 认证中间件"""

    async def dispatch(self, request: Request, call_next):
        # 检查是否豁免
        path = request.url.path
        if any(path.startswith(exempt) for exempt in EXEMPT_PATHS):
            # 豁免路径设置空上下文
            set_current_context(TenantContext())
            try:
                return await call_next(request)
            finally:
                clear_current_context()

        # 提取 token
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return JSONResponse(
                status_code=401,
                content={"code": 401, "message": "缺少认证令牌", "error_code": "AUTHENTICATION_ERROR"},
            )

        token = auth_header[7:]  # 去掉 "Bearer " 前缀

        try:
            # 从 app.state 获取 JWTService
            jwt_service = request.app.state.jwt_service
            payload = jwt_service.decode(token)

            # 注入请求上下文
            request.state.user_id = payload.get("sub")
            request.state.tenant_id = payload.get("tenant_id")
            request.state.roles = payload.get("roles", [])
            request.state.role_slugs = payload.get("role_slugs", [])
            request.state.is_superadmin = payload.get("is_superadmin", False)

            # 设置 contextvars 上下文（供下游服务直接使用）
            ctx = TenantContext(
                tenant_id=payload.get("tenant_id"),
                user_id=payload.get("sub"),
                roles=payload.get("roles", []),
                is_superadmin=payload.get("is_superadmin", False),
                is_god_mode=payload.get("god_mode", False),
            )
            set_current_context(ctx)

        except AuthenticationError as e:
            return JSONResponse(
                status_code=401,
                content={"code": 401, "message": str(e), "error_code": "AUTHENTICATION_ERROR"},
            )
        except AttributeError:
            # jwt_service 未初始化（lifespan 未完成）
            return JSONResponse(
                status_code=503,
                content={"code": 503, "message": "服务初始化中", "error_code": "SERVICE_UNAVAILABLE"},
            )

        try:
            response = await call_next(request)
            return response
        finally:
            clear_current_context()
