"""JWT 认证中间件

从 Authorization: Bearer <token> 提取 token → 验证 → 注入 request.state。
豁免路径：/health, /metrics, /api/v1/auth/login, /api/v1/users/accept-invitation
"""
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from src.core.auth.exceptions import AuthenticationError
from src.core.auth.jwt_service import JWTService
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

    def __init__(self, app, jwt_service: JWTService):
        super().__init__(app)
        self.jwt_service = jwt_service

    async def dispatch(self, request: Request, call_next):
        # 检查是否豁免
        path = request.url.path
        if any(path.startswith(exempt) for exempt in EXEMPT_PATHS):
            return await call_next(request)

        # 提取 token
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return JSONResponse(
                status_code=401,
                content={"code": 401, "message": "缺少认证令牌", "error_code": "AUTHENTICATION_ERROR"},
            )

        token = auth_header[7:]  # 去掉 "Bearer " 前缀

        try:
            # 验证 token
            payload = self.jwt_service.decode(token)

            # 注入请求上下文
            request.state.user_id = payload.get("sub")
            request.state.tenant_id = payload.get("tenant_id")
            request.state.roles = payload.get("roles", [])
            request.state.is_superadmin = payload.get("is_superadmin", False)

        except AuthenticationError as e:
            return JSONResponse(
                status_code=401,
                content={"code": 401, "message": str(e), "error_code": "AUTHENTICATION_ERROR"},
            )

        return await call_next(request)
