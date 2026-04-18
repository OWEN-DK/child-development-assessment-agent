"""测试全局异常处理器

测试 app_exception_handler, validation_exception_handler, global_exception_handler
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel

from src.middleware.exception_handler import (
    app_exception_handler,
    validation_exception_handler,
    global_exception_handler,
)
from src.utils.exceptions import (
    AppException,
    InvalidParamsException,
    ResourceNotFoundException,
    InternalServerErrorException,
)


def create_test_app():
    """创建测试应用"""
    app = FastAPI()
    app.add_exception_handler(AppException, app_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, global_exception_handler)
    return app


class TestAppExceptionHandler:
    """测试 AppException 处理器"""

    def test_handle_invalid_params(self):
        """处理参数校验异常"""
        app = create_test_app()

        @app.get("/test-invalid-params")
        def test_invalid_params():
            raise InvalidParamsException()

        with TestClient(app) as client:
            response = client.get("/test-invalid-params")
            assert response.status_code == 400
            data = response.json()
            assert data["code"] == 10001
            assert data["error_code"] == "INVALID_PARAMS"
            assert "message" in data

    def test_handle_resource_not_found(self):
        """处理资源不存在异常"""
        app = create_test_app()

        @app.get("/test-not-found")
        def test_not_found():
            raise ResourceNotFoundException()

        with TestClient(app) as client:
            response = client.get("/test-not-found")
            assert response.status_code == 404
            data = response.json()
            assert data["code"] == 10005
            assert data["error_code"] == "RESOURCE_NOT_FOUND"

    def test_handle_with_details(self):
        """处理带详细信息的异常"""
        app = create_test_app()

        @app.get("/test-details")
        def test_details():
            raise InvalidParamsException(details={"field": "name"})

        with TestClient(app) as client:
            response = client.get("/test-details")
            assert response.status_code == 400
            data = response.json()
            assert data["details"] == {"field": "name"}

    def test_handle_custom_error_code(self):
        """处理自定义错误码"""
        app = create_test_app()

        @app.get("/test-custom-code")
        def test_custom_code():
            raise ResourceNotFoundException(error_code="DOCUMENT_NOT_FOUND")

        with TestClient(app) as client:
            response = client.get("/test-custom-code")
            assert response.status_code == 404
            data = response.json()
            assert data["error_code"] == "DOCUMENT_NOT_FOUND"


class TestValidationExceptionHandler:
    """测试请求参数校验异常处理器"""

    def test_handle_validation_error(self):
        """处理参数校验失败"""
        app = create_test_app()

        class TestModel(BaseModel):
            name: str
            age: int

        @app.post("/test-validation")
        def test_validation(model: TestModel):
            return model

        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.post("/test-validation", json={"name": "test"})
            assert response.status_code == 400
            data = response.json()
            assert data["code"] == 10001
            assert data["error_code"] == "INVALID_PARAMS"
            assert "details" in data
            assert "errors" in data["details"]

    def test_validation_error_multiple_fields(self):
        """处理多字段校验失败"""
        app = create_test_app()

        class TestModel(BaseModel):
            name: str
            age: int

        @app.post("/test-validation-multi")
        def test_validation_multi(model: TestModel):
            return model

        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.post("/test-validation-multi", json={})
            assert response.status_code == 400
            data = response.json()
            assert data["code"] == 10001
            assert len(data["details"]["errors"]) == 2


class TestGlobalExceptionHandler:
    """测试全局兜底异常处理器"""

    def test_handle_unexpected_exception(self):
        """处理未预期的异常"""
        app = create_test_app()

        @app.get("/test-unexpected")
        def test_unexpected():
            raise ValueError("unexpected error")

        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.get("/test-unexpected")
            assert response.status_code == 500
            data = response.json()
            assert data["code"] == 10007
            assert data["error_code"] == "INTERNAL_ERROR"
            assert "trace_id" in data["details"]

    def test_trace_id_is_uuid(self):
        """trace_id 是有效的 UUID"""
        import uuid

        app = create_test_app()

        @app.get("/test-trace-id")
        def test_trace_id():
            raise RuntimeError("test error")

        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.get("/test-trace-id")
            data = response.json()
            trace_id = data["details"]["trace_id"]
            # 验证是有效的 UUID 格式
            uuid.UUID(trace_id)
