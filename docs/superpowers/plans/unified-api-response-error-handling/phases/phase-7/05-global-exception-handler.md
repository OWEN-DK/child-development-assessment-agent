# Phase 7-5: 全局异常处理器

> **需求来源**: spec 文档 `unified-api-response-and-error-handling.md` 中 `9.1.3-9.1.4` 节
> **所属 Phase**: Phase 7

## 需求定义

实现全局异常处理器，捕获所有未处理的异常并返回统一格式的错误响应。

## 验收标准

- [ ] `AppException` 处理器返回正确的业务码和 HTTP 状态码
- [ ] `HTTPException` 处理器兼容过渡期旧代码
- [ ] `RequestValidationError` 处理器返回 10001 错误码
- [ ] 兜底 `Exception` 处理器返回 10007 错误码
- [ ] 异常处理器注册到 FastAPI 应用

## 涉及文件

| 文件路径 | 操作 | 说明 |
|---------|------|------|
| `backend/src/middleware/exception_handler.py` | 新增 | 全局异常处理器 |
| `backend/src/server.py` | 修改 | 注册异常处理器 |

## 实现方案

### 异常处理器

```python
"""
全局异常处理器

按优先级从高到低：
1. AppException - 自定义业务异常
2. HTTPException - FastAPI HTTP 异常（过渡期兼容）
3. RequestValidationError - 请求参数校验异常
4. Exception - 兜底处理
"""

import uuid

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from src.schemas import APIResponse
from src.utils.exceptions import AppException
from src.utils.logger import logger


async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    """处理自定义应用异常"""
    logger.warning(
        "AppException: %s (%d) - %s | path=%s",
        exc.error_code,
        exc.code,
        exc.message,
        request.url.path,
    )
    return JSONResponse(
        status_code=exc.status_code,
        content=APIResponse.error(
            code=exc.code,
            message=exc.message,
            error_code=exc.error_code,
            details=exc.details,
        ),
    )


async def http_exception_handler(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    """处理 FastAPI HTTPException（兼容旧代码过渡期）"""
    logger.warning(
        "HTTPException: %d - %s | path=%s",
        exc.status_code,
        exc.detail,
        request.url.path,
    )
    # 将 HTTP 状态码映射为业务错误码
    status_to_code = {
        400: 10001,
        401: 10003,
        403: 10004,
        404: 10005,
        409: 10006,
        429: 10009,
        500: 10007,
        503: 10008,
    }
    business_code = status_to_code.get(exc.status_code, 10007)
    return JSONResponse(
        status_code=exc.status_code,
        content=APIResponse.error(
            code=business_code,
            message=str(exc.detail),
            error_code="HTTP_ERROR",
        ),
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """处理请求参数校验异常"""
    errors = exc.errors()
    messages = [f"{e.get('loc', [''])[-1]}: {e.get('msg', '')}" for e in errors]
    logger.warning(
        "RequestValidationError: %s | path=%s",
        messages,
        request.url.path,
    )
    return JSONResponse(
        status_code=400,
        content=APIResponse.error(
            code=10001,
            message="请求参数校验失败",
            error_code="INVALID_PARAMS",
            details={"errors": messages},
        ),
    )


async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """兜底处理所有未捕获异常"""
    trace_id = str(uuid.uuid4())
    logger.error(
        "Unhandled exception [trace_id=%s]: %s | path=%s",
        trace_id,
        exc,
        request.url.path,
        exc_info=True,
    )
    return JSONResponse(
        status_code=500,
        content=APIResponse.error(
            code=10007,
            message="系统内部异常，请稍后重试",
            error_code="INTERNAL_ERROR",
            details={"trace_id": trace_id},
        ),
    )
```

### 注册到 FastAPI

```python
# backend/src/server.py 中修改

from src.middleware.exception_handler import (
    app_exception_handler,
    http_exception_handler,
    validation_exception_handler,
    global_exception_handler,
)
from src.utils.exceptions import AppException
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException


def create_app() -> FastAPI:
    app = FastAPI(title="儿童发展评估 Agent", version="1.0.0")

    # 注册异常处理器（按优先级从高到低）
    app.add_exception_handler(AppException, app_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, global_exception_handler)

    # ... 其他配置
    return app
```

## 测试方案

```python
def test_app_exception_handler():
    """测试 AppException 处理"""
    exc = ResourceNotFoundException(error_code="TEST_NOT_FOUND", message="测试不存在")
    # 验证返回 HTTP 404 + {code: 10005, error_code: "TEST_NOT_FOUND"}

def test_http_exception_handler():
    """测试 HTTPException 兼容处理"""
    # 验证 HTTPException(404, "not found") 返回 {code: 10005}

def test_validation_exception_handler():
    """测试参数校验异常处理"""
    # 验证 RequestValidationError 返回 {code: 10001, details: {errors: [...]}}

def test_global_exception_handler():
    """测试兜底异常处理"""
    # 验证未捕获异常返回 {code: 10007, details: {trace_id: "..."}}
```

## 注意事项

- 处理器注册顺序不重要，FastAPI 按异常类型精确匹配
- `HTTPException` 处理器是过渡期兼容，最终应移除
- 兜底处理器生成 `trace_id` 便于排查问题
- 所有异常处理器都记录日志
