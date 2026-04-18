"""Phase 3 测试：统一响应格式

测试 APIResponse、PaginatedResponse 和异常处理体系。
"""

import pytest
from src.schemas.common import APIResponse, PaginatedResponse
from src.utils.exceptions import (
    AppException,
    InvalidParamsException,
    MissingRequiredFieldException,
    UnauthorizedException,
    ForbiddenException,
    ResourceNotFoundException,
    DuplicateResourceException,
    InternalServerErrorException,
    ServiceUnavailableException,
    RateLimitExceededException,
    TaskCancelledException,
)


class TestAPIResponse:
    """测试 APIResponse 模型"""

    def test_api_response_success(self):
        resp = APIResponse.success(data={"key": "value"})
        assert resp.code == 0
        assert resp.message == "success"
        assert resp.data == {"key": "value"}

    def test_api_response_success_with_message(self):
        resp = APIResponse.success(data=None, message="操作成功")
        assert resp.code == 0
        assert resp.message == "操作成功"
        assert resp.data is None

    def test_api_response_success_empty_data(self):
        resp = APIResponse.success()
        assert resp.code == 0
        assert resp.message == "success"
        assert resp.data is None

    def test_api_response_error(self):
        err = APIResponse.error(
            code=10001,
            message="参数错误",
            error_code="INVALID_PARAMS",
        )
        assert err["code"] == 10001
        assert err["message"] == "参数错误"
        assert err["error_code"] == "INVALID_PARAMS"
        assert "details" not in err
        assert "trace_id" not in err

    def test_api_response_error_with_details(self):
        err = APIResponse.error(
            code=10001,
            message="参数错误",
            error_code="INVALID_PARAMS",
            details={"field": "name"},
            trace_id="abc-123",
        )
        assert err["code"] == 10001
        assert err["error_code"] == "INVALID_PARAMS"
        assert err["details"] == {"field": "name"}
        assert err["trace_id"] == "abc-123"

    def test_api_response_error_default_error_code(self):
        err = APIResponse.error(code=99999, message="未知错误")
        assert err["error_code"] == "UNKNOWN_ERROR"


class TestPaginatedResponse:
    """测试 PaginatedResponse 模型"""

    def test_paginated_response_basic(self):
        page = PaginatedResponse(
            items=[1, 2, 3],
            total=100,
            page=1,
            page_size=20,
        )
        assert page.items == [1, 2, 3]
        assert page.total == 100
        assert page.page == 1
        assert page.page_size == 20

    def test_paginated_response_total_pages(self):
        page = PaginatedResponse(
            items=[],
            total=100,
            page=1,
            page_size=20,
        )
        assert page.total_pages == 5

    def test_paginated_response_has_next(self):
        page = PaginatedResponse(
            items=[],
            total=100,
            page=1,
            page_size=20,
        )
        assert page.has_next is True
        assert page.has_prev is False

    def test_paginated_response_last_page(self):
        page = PaginatedResponse(
            items=[],
            total=100,
            page=5,
            page_size=20,
        )
        assert page.has_next is False
        assert page.has_prev is True

    def test_paginated_response_empty(self):
        page = PaginatedResponse(
            items=[],
            total=0,
            page=1,
            page_size=20,
        )
        assert page.total_pages == 0
        assert page.has_next is False
        assert page.has_prev is False

    def test_paginated_response_nested_in_api_response(self):
        page = PaginatedResponse(
            items=[{"id": 1}, {"id": 2}],
            total=50,
            page=2,
            page_size=10,
        )
        resp = APIResponse.success(data=page)
        assert resp.code == 0
        assert resp.data.total == 50
        assert resp.data.page == 2
        assert len(resp.data.items) == 2


class TestExceptions:
    """测试异常类体系"""

    def test_app_exception_base(self):
        exc = AppException(
            status_code=400,
            code=10001,
            message="测试错误",
            error_code="TEST_ERROR",
            details={"key": "value"},
        )
        assert exc.status_code == 400
        assert exc.code == 10001
        assert exc.message == "测试错误"
        assert exc.error_code == "TEST_ERROR"
        assert exc.details == {"key": "value"}
        assert str(exc) == "测试错误"

    def test_invalid_params_exception(self):
        exc = InvalidParamsException()
        assert exc.status_code == 400
        assert exc.code == 10001
        assert exc.error_code == "INVALID_PARAMS"

    def test_invalid_params_exception_with_details(self):
        exc = InvalidParamsException(details={"field": "name"})
        assert exc.details == {"field": "name"}

    def test_missing_required_field_exception(self):
        exc = MissingRequiredFieldException()
        assert exc.status_code == 400
        assert exc.code == 10002
        assert exc.error_code == "MISSING_REQUIRED_FIELD"

    def test_unauthorized_exception(self):
        exc = UnauthorizedException()
        assert exc.status_code == 401
        assert exc.code == 10003
        assert exc.error_code == "UNAUTHORIZED"

    def test_forbidden_exception(self):
        exc = ForbiddenException()
        assert exc.status_code == 403
        assert exc.code == 10004
        assert exc.error_code == "FORBIDDEN"

    def test_resource_not_found_exception(self):
        exc = ResourceNotFoundException()
        assert exc.status_code == 404
        assert exc.code == 10005
        assert exc.error_code == "RESOURCE_NOT_FOUND"

    def test_resource_not_found_exception_custom_error_code(self):
        exc = ResourceNotFoundException(error_code="DOCUMENT_NOT_FOUND")
        assert exc.error_code == "DOCUMENT_NOT_FOUND"

    def test_duplicate_resource_exception(self):
        exc = DuplicateResourceException()
        assert exc.status_code == 409
        assert exc.code == 10006
        assert exc.error_code == "DUPLICATE_RESOURCE"

    def test_internal_server_error_exception(self):
        exc = InternalServerErrorException()
        assert exc.status_code == 500
        assert exc.code == 10007
        assert exc.error_code == "INTERNAL_ERROR"

    def test_service_unavailable_exception(self):
        exc = ServiceUnavailableException()
        assert exc.status_code == 503
        assert exc.code == 10008
        assert exc.error_code == "SERVICE_UNAVAILABLE"

    def test_rate_limit_exceeded_exception(self):
        exc = RateLimitExceededException()
        assert exc.status_code == 429
        assert exc.code == 10009
        assert exc.error_code == "RATE_LIMIT_EXCEEDED"

    def test_task_cancelled_exception(self):
        exc = TaskCancelledException()
        assert exc.status_code == 200
        assert exc.code == 10010
        assert exc.error_code == "TASK_CANCELLED"


class TestExceptionInheritance:
    """测试异常继承关系"""

    def test_all_exceptions_inherit_app_exception(self):
        exceptions = [
            InvalidParamsException(),
            MissingRequiredFieldException(),
            UnauthorizedException(),
            ForbiddenException(),
            ResourceNotFoundException(),
            DuplicateResourceException(),
            InternalServerErrorException(),
            ServiceUnavailableException(),
            RateLimitExceededException(),
            TaskCancelledException(),
        ]
        for exc in exceptions:
            assert isinstance(exc, AppException)
