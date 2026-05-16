"""SearchAuthService 单元测试

测试 JWT / API Key / none 三种认证方式。
"""
import pytest
from unittest.mock import MagicMock

from fastapi import Request

from src.core.auth.exceptions import AuthenticationError
from src.models.published_endpoint import PublishedEndpoint
from src.schemas.search.auth import SearchAuthContext
from src.service.search.search_auth_service import SearchAuthService


@pytest.fixture
def jwt_service():
    """Mock JWT 服务"""
    svc = MagicMock()
    svc.decode.return_value = {
        "user_id": "user-001",
        "tenant_id": "tenant-001",
        "roles": ["admin", "editor"],
    }
    return svc


@pytest.fixture
def auth_service(jwt_service):
    return SearchAuthService(jwt_service)


def _make_request(headers: dict) -> Request:
    """构建 mock Request（ASGI scope 要求 headers 的 key 为小写 bytes）"""
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/search/test",
        "headers": [(k.lower().encode(), v.encode()) for k, v in headers.items()],
    }
    return Request(scope=scope)


def _make_endpoint(auth_type: str = "jwt", tenant_id: str = "tenant-001") -> PublishedEndpoint:
    """构建 PublishedEndpoint 测试实例"""
    return PublishedEndpoint(
        id=1,
        endpoint_id="ep-001",
        pipeline_id="pipe-001",
        tenant_id=tenant_id,
        url_path="test-endpoint",
        bound_version=1,
        http_method="POST",
        auth_type=auth_type,
        rate_limit=0,
        enabled=True,
        allowed_params=["top_k"],
        response_format="json",
    )


class TestSearchAuthService:
    """搜索认证服务测试"""

    @pytest.mark.asyncio
    async def test_jwt_auth_valid(self, auth_service):
        """有效 JWT token 返回完整 AuthContext"""
        request = _make_request({"Authorization": "Bearer valid-jwt-token"})
        endpoint = _make_endpoint(auth_type="jwt")

        ctx = await auth_service.authenticate(request, endpoint)
        assert isinstance(ctx, SearchAuthContext)
        assert ctx.authenticated is True
        assert ctx.user_id == "user-001"
        assert ctx.tenant_id == "tenant-001"
        assert ctx.roles == ["admin", "editor"]
        assert ctx.auth_method == "jwt"

    @pytest.mark.asyncio
    async def test_jwt_auth_expired(self, auth_service, jwt_service):
        """过期 JWT token 抛出 AuthenticationError"""
        jwt_service.decode.side_effect = Exception("Token expired")

        request = _make_request({"Authorization": "Bearer expired-token"})
        endpoint = _make_endpoint(auth_type="jwt")

        with pytest.raises(AuthenticationError) as exc:
            await auth_service.authenticate(request, endpoint)
        assert exc.value.error_code == "AUTH_FAILED"

    @pytest.mark.asyncio
    async def test_jwt_auth_missing(self, auth_service):
        """无 Authorization header 时抛出 AUTH_TYPE_MISMATCH"""
        request = _make_request({})
        endpoint = _make_endpoint(auth_type="jwt")

        with pytest.raises(AuthenticationError) as exc:
            await auth_service.authenticate(request, endpoint)
        assert exc.value.error_code == "AUTH_TYPE_MISMATCH"

    @pytest.mark.asyncio
    async def test_api_key_auth_via_header(self, auth_service):
        """通过 X-Api-Key header 认证"""
        request = _make_request({"X-Api-Key": "sk-test-api-key"})
        endpoint = _make_endpoint(auth_type="api_key")

        ctx = await auth_service.authenticate(request, endpoint)
        assert ctx.authenticated is True
        assert ctx.auth_method == "api_key"
        assert ctx.tenant_id == "tenant-001"

    @pytest.mark.asyncio
    async def test_api_key_auth_via_authorization(self, auth_service):
        """通过 Authorization: ApiKey header 认证"""
        request = _make_request({"Authorization": "ApiKey sk-test-api-key"})
        endpoint = _make_endpoint(auth_type="api_key")

        ctx = await auth_service.authenticate(request, endpoint)
        assert ctx.authenticated is True
        assert ctx.auth_method == "api_key"

    @pytest.mark.asyncio
    async def test_api_key_empty_string(self, auth_service):
        """API Key 为空字符串 → AUTH_TYPE_MISMATCH"""
        request = _make_request({"X-Api-Key": ""})
        endpoint = _make_endpoint(auth_type="api_key")

        with pytest.raises(AuthenticationError) as exc:
            await auth_service.authenticate(request, endpoint)
        assert exc.value.error_code == "AUTH_TYPE_MISMATCH"

    @pytest.mark.asyncio
    async def test_auth_type_none(self, auth_service):
        """auth_type=none 返回匿名上下文"""
        request = _make_request({})
        endpoint = _make_endpoint(auth_type="none")

        ctx = await auth_service.authenticate(request, endpoint)
        assert ctx.authenticated is False
        assert ctx.roles == []
        assert ctx.auth_method == "none"

    @pytest.mark.asyncio
    async def test_auth_type_mismatch(self, auth_service):
        """端点要求 jwt 但发送 API Key → AUTH_TYPE_MISMATCH"""
        request = _make_request({"X-Api-Key": "sk-test-key"})
        endpoint = _make_endpoint(auth_type="jwt")

        with pytest.raises(AuthenticationError) as exc:
            await auth_service.authenticate(request, endpoint)
        assert exc.value.error_code == "AUTH_TYPE_MISMATCH"

    @pytest.mark.asyncio
    async def test_api_key_missing_for_api_key_endpoint(self, auth_service):
        """端点要求 api_key 但无凭据 → AUTH_TYPE_MISMATCH"""
        request = _make_request({})
        endpoint = _make_endpoint(auth_type="api_key")

        with pytest.raises(AuthenticationError) as exc:
            await auth_service.authenticate(request, endpoint)
        assert exc.value.error_code == "AUTH_TYPE_MISMATCH"
