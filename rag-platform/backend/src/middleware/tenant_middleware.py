"""租户状态中间件

检查 request.state.tenant_id 对应的租户状态：
- active → 放行
- disabled → 403 TenantSuspendedError
- archived → 403 TenantSuspendedError
"""
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from src.utils.logger import logger


class TenantMiddleware(BaseHTTPMiddleware):
    """租户状态检查中间件"""

    async def dispatch(self, request: Request, call_next):
        # 超管无 tenant_id，跳过检查
        tenant_id = getattr(request.state, "tenant_id", None)
        if tenant_id is None:
            return await call_next(request)

        # 查询租户状态
        try:
            tenant_repo = request.app.state.tenant_repo
            tenant = await tenant_repo.get_by_id(tenant_id)

            if tenant is None:
                return JSONResponse(
                    status_code=404,
                    content={"code": 404, "message": "租户不存在", "error_code": "TENANT_NOT_FOUND"},
                )

            if tenant.status in ("disabled", "archived"):
                return JSONResponse(
                    status_code=403,
                    content={
                        "code": 403,
                        "message": "租户已停用或归档",
                        "error_code": "TENANT_SUSPENDED",
                    },
                )

            if tenant.status == "deleted":
                return JSONResponse(
                    status_code=404,
                    content={"code": 404, "message": "租户已删除", "error_code": "TENANT_NOT_FOUND"},
                )

        except AttributeError:
            # tenant_repo 未初始化（lifespan 未完成）
            return JSONResponse(
                status_code=503,
                content={"code": 503, "message": "服务初始化中", "error_code": "SERVICE_UNAVAILABLE"},
            )
        except Exception as e:
            logger.error(f"租户状态检查异常: {e}")
            return JSONResponse(
                status_code=500,
                content={"code": 500, "message": "内部错误", "error_code": "INTERNAL_ERROR"},
            )

        return await call_next(request)
