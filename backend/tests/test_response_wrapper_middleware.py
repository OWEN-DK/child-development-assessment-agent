"""测试响应包装中间件

测试 ResponseWrapperMiddleware 自动包装成功响应
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.responses import JSONResponse, StreamingResponse

from src.middleware.response_wrapper import ResponseWrapperMiddleware


def create_test_app():
    """创建测试应用"""
    app = FastAPI()
    app.add_middleware(ResponseWrapperMiddleware)
    return app


class TestResponseWrapperMiddleware:
    """测试响应包装中间件"""

    def test_wrap_dict_response(self):
        """包装字典响应"""
        app = create_test_app()

        @app.get("/test-dict")
        def test_dict():
            return {"name": "test", "value": 123}

        with TestClient(app) as client:
            response = client.get("/test-dict")
            assert response.status_code == 200
            data = response.json()
            assert data["code"] == 0
            assert data["message"] == "success"
            assert data["data"] == {"name": "test", "value": 123}

    def test_wrap_list_response(self):
        """包装列表响应"""
        app = create_test_app()

        @app.get("/test-list")
        def test_list():
            return [1, 2, 3, 4, 5]

        with TestClient(app) as client:
            response = client.get("/test-list")
            assert response.status_code == 200
            data = response.json()
            assert data["code"] == 0
            assert data["data"] == [1, 2, 3, 4, 5]

    def test_skip_already_wrapped(self):
        """跳过已包装的响应"""
        app = create_test_app()

        @app.get("/test-already-wrapped")
        def test_already_wrapped():
            return {"code": 0, "message": "success", "data": {"key": "value"}}

        with TestClient(app) as client:
            response = client.get("/test-already-wrapped")
            assert response.status_code == 200
            data = response.json()
            # 不应该被二次包装
            assert data["code"] == 0
            assert data["data"] == {"key": "value"}
            # 如果是二次包装，data 会是 {"code": 0, "message": "success", "data": {...}}
            assert "code" not in data.get("data", {}) or data["data"].get("key") == "value"

    def test_skip_error_response(self):
        """跳过错误响应"""
        app = create_test_app()

        @app.get("/test-error")
        def test_error():
            return JSONResponse(
                status_code=400,
                content={"code": 10001, "message": "参数错误", "error_code": "INVALID_PARAMS"},
            )

        with TestClient(app) as client:
            response = client.get("/test-error")
            assert response.status_code == 400
            data = response.json()
            # 错误响应不应该被包装
            assert data["code"] == 10001
            assert "data" not in data

    def test_skip_204_response(self):
        """跳过 204 响应"""
        app = create_test_app()

        @app.get("/test-204")
        def test_204():
            return JSONResponse(status_code=204, content=None)

        with TestClient(app) as client:
            response = client.get("/test-204")
            assert response.status_code == 204

    def test_skip_304_response(self):
        """跳过 304 响应"""
        app = create_test_app()

        @app.get("/test-304")
        def test_304():
            return JSONResponse(status_code=304, content=None)

        with TestClient(app) as client:
            response = client.get("/test-304")
            assert response.status_code == 304

    def test_wrap_nested_data(self):
        """包装嵌套数据结构"""
        app = create_test_app()

        @app.get("/test-nested")
        def test_nested():
            return {
                "user": {"name": "test", "age": 25},
                "items": [{"id": 1}, {"id": 2}],
            }

        with TestClient(app) as client:
            response = client.get("/test-nested")
            assert response.status_code == 200
            data = response.json()
            assert data["code"] == 0
            assert data["data"]["user"]["name"] == "test"
            assert len(data["data"]["items"]) == 2
