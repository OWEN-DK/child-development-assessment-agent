"""动态搜索路由管理器

运行时动态注册/移除搜索路由。
采用"逻辑移除"策略：从内存路由表删除映射，handler 入口检查返回 404。
"""
import json
from typing import Any, Callable, Optional

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from src.api.json_response import UtcJsonResponse
from src.core.pipeline.compiler import PipelineCompiler
from src.core.pipeline.node_context import AuthContext
from src.repository.pipeline.pipeline_repo import PipelineRepository
from src.repository.search.publish_repo import PublishedEndpointRepository
from src.schemas.search.response import SearchResponse
from src.service.search.rate_limit_service import RateLimitService
from src.service.search.search_auth_service import SearchAuthService
from src.service.search.search_service import SearchService
from src.utils.logger import logger


class DynamicSearchRouter:
    """动态搜索路由管理器

    支持两阶段初始化：
    1. create_app() 中创建空实例 + include_router
    2. lifespan 中 configure() 注入真实依赖 + load_all_on_startup()
    """

    def __init__(self):
        self._search_service = None
        self._auth_service = None
        self._rate_limit_service = None
        self._publish_repo = None
        self._pipeline_repo = None

        self.router = APIRouter(tags=["动态搜索"])
        # url_path → endpoint_id 映射（逻辑路由表）
        self._routes: dict[str, str] = {}

    def configure(
        self,
        search_service: SearchService,
        auth_service: SearchAuthService,
        rate_limit_service: RateLimitService,
        publish_repo: PublishedEndpointRepository,
        pipeline_repo: PipelineRepository,
    ) -> None:
        """注入依赖（在 lifespan 中调用）"""
        self._search_service = search_service
        self._auth_service = auth_service
        self._rate_limit_service = rate_limit_service
        self._publish_repo = publish_repo
        self._pipeline_repo = pipeline_repo

    async def load_all_on_startup(self) -> None:
        """启动时加载所有启用的端点"""
        try:
            endpoints = await self._publish_repo.list_enabled()
            for ep in endpoints:
                try:
                    self._register_route(ep)
                except Exception as e:
                    logger.error(f"加载端点失败 {ep.url_path}: {e}")
            logger.info(f"动态搜索路由加载完成: {len(self._routes)} 个端点")
        except Exception as e:
            logger.error(f"动态路由加载失败: {e}")

    def _register_route(self, endpoint) -> None:
        """注册单个搜索路由"""
        url_path = endpoint.url_path
        handler = self._build_handler(endpoint)

        # 注册到 FastAPI router
        self.router.add_api_route(
            path=f"/search/{url_path}",
            endpoint=handler,
            methods=[endpoint.http_method],
            summary=f"搜索端点: {url_path}",
        )
        self._routes[url_path] = endpoint.endpoint_id
        logger.info(f"动态路由注册: /search/{url_path} → {endpoint.endpoint_id}")

    def unregister_route(self, url_path: str) -> None:
        """逻辑移除路由"""
        if url_path in self._routes:
            del self._routes[url_path]
            logger.info(f"动态路由移除: /search/{url_path}")

    def reload_route(self, endpoint) -> None:
        """重载路由（版本切换用）"""
        self.unregister_route(endpoint.url_path)
        self._register_route(endpoint)

    def list_registered_routes(self) -> list[dict[str, str]]:
        """列出当前活跃路由"""
        return [
            {"url_path": path, "endpoint_id": eid}
            for path, eid in self._routes.items()
        ]

    def _build_handler(self, endpoint) -> Callable:
        """为每个端点构建独立的 handler 闭包"""
        url_path = endpoint.url_path
        endpoint_id = endpoint.endpoint_id
        pipeline_id = endpoint.pipeline_id
        bound_version = endpoint.bound_version
        auth_type = endpoint.auth_type
        max_qps = endpoint.rate_limit
        allowed_params = endpoint.allowed_params
        tenant_id = endpoint.tenant_id

        async def handler(request: Request):
            # 逻辑移除检查
            if url_path not in self._routes:
                return UtcJsonResponse(
                    status_code=404,
                    content={"code": 404, "message": "搜索端点不存在", "error_code": "ENDPOINT_NOT_FOUND"},
                )

            # 查询端点状态
            ep = await self._publish_repo.get_by_url_path(url_path)
            if not ep or not ep.enabled:
                return UtcJsonResponse(
                    status_code=404,
                    content={"code": 404, "message": "该搜索端点已停用", "error_code": "ENDPOINT_DISABLED"},
                )

            # 认证
            try:
                auth_ctx = await self._auth_service.authenticate(request, ep)
            except Exception as e:
                return UtcJsonResponse(
                    status_code=401,
                    content={"code": 401, "message": str(e), "error_code": "AUTH_FAILED"},
                )

            # 限流
            if max_qps > 0:
                rl_result = await self._rate_limit_service.check_and_consume(
                    endpoint_id, max_qps, auth_ctx.tenant_id, auth_ctx.user_id
                )
                if not rl_result.allowed:
                    return UtcJsonResponse(
                        status_code=429,
                        content={
                            "code": 429,
                            "message": "请求过于频繁，请稍后重试",
                            "error_code": "RATE_LIMITED",
                            "details": {
                                "limit_type": rl_result.limit_type,
                                "max_qps": max_qps,
                                "retry_after_ms": rl_result.reset_after_ms,
                            },
                        },
                        headers={
                            "Retry-After": str(rl_result.reset_after_ms // 1000 + 1),
                            "X-RateLimit-Limit": str(max_qps),
                            "X-RateLimit-Remaining": str(rl_result.remaining),
                        },
                    )

            # 解析请求体
            try:
                body = await request.json()
            except Exception:
                body = {}

            query = body.get("query", "")
            if not query:
                return UtcJsonResponse(
                    status_code=400,
                    content={"code": 400, "message": "查询文本不能为空", "error_code": "QUERY_EMPTY"},
                )
            if len(query) > 2000:
                return UtcJsonResponse(
                    status_code=400,
                    content={"code": 400, "message": "查询文本超过 2000 字符限制", "error_code": "QUERY_TOO_LONG"},
                )

            params = body.get("params", {})

            # 获取管道配置
            pipeline = await self._pipeline_repo.get_by_id(pipeline_id, tenant_id)
            if not pipeline:
                return UtcJsonResponse(
                    status_code=404,
                    content={"code": 404, "message": "管道不存在", "error_code": "PIPELINE_NOT_FOUND"},
                )

            # 获取绑定版本的配置
            from src.repository.pipeline.version_repo import PipelineVersionRepository
            version_repo = PipelineVersionRepository(self._publish_repo.db_session_factory)
            version = await version_repo.get_by_version(pipeline_id, bound_version, tenant_id)
            if not version:
                return UtcJsonResponse(
                    status_code=400,
                    content={"code": 400, "message": f"版本 v{bound_version} 不存在", "error_code": "PIPELINE_CONFIG_INVALID"},
                )

            pipeline_config = json.loads(version.config_snapshot)

            # 构建认证上下文
            auth = AuthContext(
                tenant_id=auth_ctx.tenant_id,
                user_id=auth_ctx.user_id,
                roles=auth_ctx.roles,
                role_slugs=getattr(auth_ctx, "role_slugs", []),
                is_superadmin=False,
            )

            # 执行搜索
            result = await self._search_service.sync_search(
                pipeline_config=pipeline_config,
                query=query,
                params=params,
                auth=auth,
                allowed_param_whitelist=allowed_params if allowed_params else None,
            )

            return UtcJsonResponse(content={"code": 0, "message": "success", "data": result.model_dump()})

        return handler
