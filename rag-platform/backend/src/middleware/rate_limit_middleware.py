"""速率限制中间件

两层独立限流：
1. 发布端点级：按端点配置的 max_qps 限流
2. 用户级：按用户 ID 独立限流（防止单用户滥用）

滑动窗口日志算法，Redis 模式（Sorted Set）+ 内存降级（deque）。
"""
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from src.schemas.common import APIResponse
from src.schemas.search.rate_limit import RateLimitResult
from src.utils.logger import logger

# 限流检查的路径前缀
RATE_LIMIT_PATHS = [
    "/search/",
    "/api/v1/search",
]

# 用户级默认限流（QPS）
DEFAULT_USER_QPS = 50


class RateLimitMiddleware(BaseHTTPMiddleware):
    """速率限制中间件

    集成到中间件链：Trace → ResponseWrapper → Auth → Tenant → RateLimit → CORS。
    仅对搜索路径生效，其他路径跳过。
    从 request.app.state 获取 rate_limit_service 依赖。
    """

    async def dispatch(self, request: Request, call_next):
        rate_limit_service = getattr(request.app.state, "rate_limit_service", None)
        if rate_limit_service is None:
            return await call_next(request)
        path = request.url.path

        # 仅对搜索路径进行限流
        if not any(path.startswith(prefix) for prefix in RATE_LIMIT_PATHS):
            return await call_next(request)

        # 提取上下文信息
        tenant_id = getattr(request.state, "tenant_id", None) or "anonymous"
        user_id = getattr(request.state, "user_id", None) or "anonymous"
        endpoint_id = self._extract_endpoint_id(path)

        # 1. 端点级限流
        max_qps = self._get_endpoint_qps(request, endpoint_id)
        if max_qps > 0:
            result = await rate_limit_service.check_and_consume(
                endpoint_id=endpoint_id,
                max_qps=max_qps,
                tenant_id=tenant_id,
                user_id=user_id,
            )
            if not result.allowed:
                return self._rate_limited_response(result, "端点级限流")

        # 2. 用户级限流
        user_result = await rate_limit_service.check_and_consume(
            endpoint_id=f"user:{user_id}",
            max_qps=DEFAULT_USER_QPS,
            tenant_id=tenant_id,
            user_id=user_id,
        )
        if not user_result.allowed:
            return self._rate_limited_response(user_result, "用户级限流")

        return await call_next(request)

    def _extract_endpoint_id(self, path: str) -> str:
        """从路径提取端点 ID

        /search/medical-consultation → medical-consultation
        /api/v1/search → api_v1_search
        """
        if path.startswith("/search/"):
            return path[len("/search/"):].split("?")[0].split("/")[0]
        return "api_v1_search"

    def _get_endpoint_qps(self, request: Request, endpoint_id: str) -> int:
        """获取端点的限流 QPS 配置

        优先从 request.state 的动态路由配置读取，
        其次从管道发布配置读取。
        """
        # 从动态路由配置中获取（由 DynamicSearchRouter 注入）
        route_config = getattr(request.state, "route_config", None)
        if route_config and isinstance(route_config, dict):
            qps = route_config.get("rate_limit", 0)
            if qps:
                return int(qps)

        # 默认：不限流（0=unlimited）
        return 0

    def _rate_limited_response(
        self, result: RateLimitResult, limit_level: str
    ) -> JSONResponse:
        """构建 429 Too Many Requests 响应"""
        return JSONResponse(
            status_code=429,
            content=APIResponse.error(
                code=429,
                message=f"请求过多，请 {result.reset_after_ms}ms 后重试",
                error_code="RATE_LIMIT_EXCEEDED",
                details={
                    "limit_type": result.limit_type,
                    "limit_level": limit_level,
                    "reset_after_ms": result.reset_after_ms,
                },
            ),
            headers={
                "Retry-After": str(result.reset_after_ms // 1000 + 1),
                "X-RateLimit-Remaining": str(result.remaining),
            },
        )
