"""DynamicSearchRouter 单元测试

测试动态路由注册/移除/重载/列表。
Mock 所有依赖服务。
"""
import pytest
from unittest.mock import AsyncMock, MagicMock

from src.service.search.dynamic_search_router import DynamicSearchRouter


@pytest.fixture
def router():
    """构建 DynamicSearchRouter 测试实例"""
    r = DynamicSearchRouter()
    r.configure(
        search_service=MagicMock(),
        auth_service=MagicMock(),
        rate_limit_service=MagicMock(),
        publish_repo=MagicMock(),
        pipeline_repo=MagicMock(),
    )
    return r


def _fake_endpoint(**overrides):
    """构造 mock 端点"""
    ep = MagicMock()
    ep.endpoint_id = overrides.get("endpoint_id", "ep-001")
    ep.url_path = overrides.get("url_path", "test-endpoint")
    ep.pipeline_id = overrides.get("pipeline_id", "pipe-001")
    ep.bound_version = overrides.get("bound_version", 1)
    ep.tenant_id = overrides.get("tenant_id", "tenant-001")
    ep.http_method = overrides.get("http_method", "POST")
    ep.auth_type = overrides.get("auth_type", "jwt")
    ep.rate_limit = overrides.get("rate_limit", 0)
    ep.enabled = overrides.get("enabled", True)
    ep.allowed_params = overrides.get("allowed_params", [])
    return ep


class TestDynamicSearchRouter:
    """动态路由管理测试"""

    def test_initial_routes_empty(self, router):
        """初始状态无路由"""
        assert router._routes == {}
        assert router.list_registered_routes() == []

    def test_register_route(self, router):
        """注册新搜索路由——_routes 包含新映射"""
        ep = _fake_endpoint(url_path="medical")
        router._register_route(ep)

        assert "medical" in router._routes
        assert router._routes["medical"] == "ep-001"

    def test_register_multiple_routes(self, router):
        """注册多个路由——全部在 _routes 中"""
        router._register_route(_fake_endpoint(url_path="path-a", endpoint_id="ep-a"))
        router._register_route(_fake_endpoint(url_path="path-b", endpoint_id="ep-b"))

        assert len(router._routes) == 2
        assert "path-a" in router._routes
        assert "path-b" in router._routes

    def test_register_duplicate_path_overwrites(self, router):
        """重复注册同一路径——覆盖旧路由"""
        router._register_route(_fake_endpoint(url_path="same", endpoint_id="ep-old"))
        router._register_route(_fake_endpoint(url_path="same", endpoint_id="ep-new"))

        assert router._routes["same"] == "ep-new"

    def test_unregister_route(self, router):
        """移除路由——_routes 不含该映射"""
        router._register_route(_fake_endpoint(url_path="to-remove"))
        router.unregister_route("to-remove")

        assert "to-remove" not in router._routes

    def test_unregister_nonexistent_no_error(self, router):
        """移除不存在的路由——不抛异常"""
        router.unregister_route("nonexistent")  # 不抛异常

    def test_reload_route(self, router):
        """重载路由——先移除后注册"""
        old_ep = _fake_endpoint(url_path="reload-path", endpoint_id="ep-old")
        router._register_route(old_ep)

        new_ep = _fake_endpoint(url_path="reload-path", endpoint_id="ep-new")
        router.reload_route(new_ep)

        assert router._routes["reload-path"] == "ep-new"

    def test_list_registered_routes(self, router):
        """列出所有活跃路由"""
        router._register_route(_fake_endpoint(url_path="path-a", endpoint_id="ep-a"))
        router._register_route(_fake_endpoint(url_path="path-b", endpoint_id="ep-b"))

        routes = router.list_registered_routes()
        assert len(routes) == 2
        assert {"url_path": "path-a", "endpoint_id": "ep-a"} in routes
        assert {"url_path": "path-b", "endpoint_id": "ep-b"} in routes

    def test_build_handler_creates_callable(self, router):
        """_build_handler 返回 async callable"""
        ep = _fake_endpoint()
        handler = router._build_handler(ep)

        assert callable(handler)

    @pytest.mark.asyncio
    async def test_handler_rejects_disabled_endpoint(self, router):
        """handler 检查 enabled=False 时返回 404"""
        router._register_route(_fake_endpoint(url_path="test", endpoint_id="ep-001"))

        # Mock publish_repo 返回 disabled 端点
        ep = _fake_endpoint(url_path="test", enabled=False)
        router._publish_repo.get_by_url_path = AsyncMock(return_value=ep)

        handler = router._build_handler(ep)

        from fastapi import Request
        scope = {
            "type": "http", "method": "POST", "path": "/search/test",
            "headers": [(b"content-type", b"application/json")],
        }
        request = Request(scope=scope)
        response = await handler(request)

        assert response.status_code == 404
        import json
        body = json.loads(response.body)
        assert body["error_code"] == "ENDPOINT_DISABLED"

    @pytest.mark.asyncio
    async def test_handler_rejects_removed_route(self, router):
        """handler 检查路由已移除时返回 404"""
        ep = _fake_endpoint(url_path="removed")
        # 先注册再移除
        router._register_route(ep)
        router.unregister_route("removed")

        handler = router._build_handler(ep)

        from fastapi import Request
        scope = {
            "type": "http", "method": "POST", "path": "/search/removed",
            "headers": [(b"content-type", b"application/json")],
        }
        request = Request(scope=scope)
        response = await handler(request)

        assert response.status_code == 404
        import json
        body = json.loads(response.body)
        assert body["error_code"] == "ENDPOINT_NOT_FOUND"
