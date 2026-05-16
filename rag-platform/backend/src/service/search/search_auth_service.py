"""搜索认证服务

支持 JWT 和 API Key 双模式认证。
认证方式不匹配时抛出 AuthFailedError。
"""
from typing import Optional

from fastapi import Request

from src.core.auth.exceptions import AuthenticationError
from src.core.auth.jwt_service import JWTService
from src.models.published_endpoint import PublishedEndpoint
from src.schemas.search.auth import SearchAuthContext
from src.utils.logger import logger


class SearchAuthService:
    """搜索认证服务"""

    def __init__(self, jwt_service: JWTService):
        self._jwt_service = jwt_service

    async def authenticate(
        self, request: Request, endpoint: PublishedEndpoint
    ) -> SearchAuthContext:
        """根据端点配置的认证方式进行认证

        Args:
            request: FastAPI 请求
            endpoint: 发布端点

        Returns:
            SearchAuthContext 认证上下文

        Raises:
            AuthenticationError: 认证失败或方式不匹配
        """
        auth_type = endpoint.auth_type

        if auth_type == "none":
            return self._no_auth_context(endpoint.tenant_id)

        # 提取凭据
        auth_header = request.headers.get("authorization", "")
        api_key = request.headers.get("x-api-key", "")

        has_jwt = auth_header.startswith("Bearer ")
        has_api_key = bool(api_key) or auth_header.startswith("ApiKey ")

        if auth_type == "jwt":
            if not has_jwt:
                raise AuthenticationError(
                    status_code=401,
                    code=401,
                    message="该端点要求 JWT 认证，请提供 Authorization: Bearer <token>",
                    error_code="AUTH_TYPE_MISMATCH",
                )
            return await self._authenticate_jwt(auth_header)

        if auth_type == "api_key":
            if not has_api_key:
                raise AuthenticationError(
                    status_code=401,
                    code=401,
                    message="该端点要求 API Key 认证，请提供 X-Api-Key 或 Authorization: ApiKey <key>",
                    error_code="AUTH_TYPE_MISMATCH",
                )
            key = api_key or auth_header.replace("ApiKey ", "").strip()
            return await self._authenticate_api_key(key, endpoint.tenant_id)

        raise AuthenticationError(
            status_code=401,
            code=401,
            message=f"不支持的认证类型: {auth_type}",
            error_code="AUTH_FAILED",
        )

    async def _authenticate_jwt(self, auth_header: str) -> SearchAuthContext:
        """JWT 认证"""
        token = auth_header.replace("Bearer ", "").strip()
        try:
            payload = self._jwt_service.decode(token)
            return SearchAuthContext(
                authenticated=True,
                user_id=payload.get("sub", "") or payload.get("user_id", ""),
                tenant_id=payload.get("tenant_id", ""),
                roles=payload.get("roles", []),
                role_slugs=payload.get("role_slugs", []),
                auth_method="jwt",
            )
        except Exception as e:
            raise AuthenticationError(
                status_code=401,
                code=401,
                message=f"JWT 认证失败: {e}",
                error_code="AUTH_FAILED",
            )

    async def _authenticate_api_key(
        self, api_key: str, tenant_id: str
    ) -> SearchAuthContext:
        """API Key 认证

        TODO: 实际实现需查询 api_keys 表关联租户和角色。
        当前为简化实现，返回基于 tenant_id 的上下文。
        """
        if not api_key:
            raise AuthenticationError(
                status_code=401,
                code=401,
                message="API Key 不能为空",
                error_code="AUTH_FAILED",
            )

        # 简化实现：API Key 有效即返回租户上下文
        # 完整实现应查询 api_keys 表获取 user_id 和 roles
        return SearchAuthContext(
            authenticated=True,
            user_id="",
            tenant_id=tenant_id,
            roles=[],
            auth_method="api_key",
        )

    def _no_auth_context(self, tenant_id: str) -> SearchAuthContext:
        """匿名认证上下文"""
        return SearchAuthContext(
            authenticated=False,
            user_id="",
            tenant_id=tenant_id,
            roles=[],
            auth_method="none",
        )
