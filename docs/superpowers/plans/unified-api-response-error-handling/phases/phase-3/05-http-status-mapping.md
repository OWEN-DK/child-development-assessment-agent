# Phase 3-5: HTTP 状态码映射

> **需求来源**: spec 文档 `unified-api-response-and-error-handling.md` 中 `4.4` 节
> **所属 Phase**: Phase 3

## 需求定义

定义 HTTP 状态码与业务错误码的映射关系，保持 HTTP 语义的同时提供细粒度的业务判断。

## 验收标准

- [ ] HTTP 状态码与业务码映射表定义完整
- [ ] 异常类自动设置正确的 HTTP 状态码
- [ ] 前端能同时使用 HTTP 状态码和业务码判断

## 涉及文件

| 文件路径 | 操作 | 说明 |
|---------|------|------|
| `backend/src/utils/exceptions.py` | 修改 | 异常类携带 HTTP 状态码 |
| `backend/src/middleware/exception_handler.py` | 新建 | 异常处理器使用 HTTP 状态码 |

## 实现方案

### HTTP 状态码与业务码映射表

| HTTP 状态码 | 使用场景 | 业务码范围 | 典型错误码 |
|------------|---------|-----------|-----------|
| `200` | 请求成功 | `code: 0` | `SUCCESS` |
| `400` | 参数校验失败、业务规则不通过 | `10001-10099` | `INVALID_PARAMS`, `MISSING_REQUIRED_FIELD` |
| `401` | 未认证或 Token 过期 | `10003` | `UNAUTHORIZED` |
| `403` | 权限不足 | `10004` | `FORBIDDEN` |
| `404` | 资源不存在 | `10005` + 模块码 | `RESOURCE_NOT_FOUND`, `DOCUMENT_NOT_FOUND` |
| `409` | 资源冲突/重复 | `10006` | `DUPLICATE_RESOURCE` |
| `429` | 请求频率超限 | `10009` | `RATE_LIMIT_EXCEEDED` |
| `500` | 服务端内部异常 | `10007` | `INTERNAL_ERROR` |
| `503` | 依赖服务不可用 | `10008` | `SERVICE_UNAVAILABLE` |

### 异常类定义（携带 HTTP 状态码）

```python
"""
自定义业务异常
"""

from typing import Optional


class AppException(Exception):
    """应用异常基类，携带 HTTP 状态码和业务错误码"""
    
    def __init__(
        self,
        status_code: int,
        code: int,
        message: str,
        error_code: str = "APP_ERROR",
        details: Optional[dict] = None,
    ):
        self.status_code = status_code    # HTTP 状态码
        self.code = code                  # 业务错误码（数字）
        self.message = message            # 用户可读信息（中文）
        self.error_code = error_code      # 错误码标识（英文大写蛇形）
        self.details = details            # 额外上下文
        super().__init__(message)


# === 通用异常 ===

class InvalidParamsException(AppException):
    """参数校验失败"""
    def __init__(self, message: str = "请求参数校验失败", details: Optional[dict] = None):
        super().__init__(
            status_code=400,
            code=10001,
            message=message,
            error_code="INVALID_PARAMS",
            details=details,
        )


class ResourceNotFoundException(AppException):
    """资源不存在"""
    def __init__(
        self,
        message: str = "请求的资源不存在",
        error_code: str = "RESOURCE_NOT_FOUND",
        details: Optional[dict] = None,
    ):
        super().__init__(
            status_code=404,
            code=10005,
            message=message,
            error_code=error_code,
            details=details,
        )


class UnauthorizedException(AppException):
    """未授权"""
    def __init__(self, message: str = "未授权，请先登录"):
        super().__init__(
            status_code=401,
            code=10003,
            message=message,
            error_code="UNAUTHORIZED",
        )


class ForbiddenException(AppException):
    """权限不足"""
    def __init__(self, message: str = "无权限执行此操作"):
        super().__init__(
            status_code=403,
            code=10004,
            message=message,
            error_code="FORBIDDEN",
        )


class DuplicateResourceException(AppException):
    """资源重复"""
    def __init__(self, message: str = "资源已存在", details: Optional[dict] = None):
        super().__init__(
            status_code=409,
            code=10006,
            message=message,
            error_code="DUPLICATE_RESOURCE",
            details=details,
        )


class InternalServerErrorException(AppException):
    """系统内部异常"""
    def __init__(self, message: str = "系统内部异常，请稍后重试"):
        super().__init__(
            status_code=500,
            code=10007,
            message=message,
            error_code="INTERNAL_ERROR",
        )


class ServiceUnavailableException(AppException):
    """服务不可用"""
    def __init__(self, message: str = "服务暂时不可用"):
        super().__init__(
            status_code=503,
            code=10008,
            message=message,
            error_code="SERVICE_UNAVAILABLE",
        )
```

### 异常处理器使用 HTTP 状态码

```python
from fastapi import Request
from fastapi.responses import JSONResponse
from src.utils.exceptions import AppException
from src.schemas import APIResponse

async def app_exception_handler(request: Request, exc: AppException):
    """处理自定义应用异常，使用 exc.status_code 作为 HTTP 状态码"""
    return JSONResponse(
        status_code=exc.status_code,  # 使用异常自带的 HTTP 状态码
        content=APIResponse.error(
            code=exc.code,
            message=exc.message,
            error_code=exc.error_code,
            details=exc.details,
        ),
    )
```

## 测试方案

1. `InvalidParamsException` 返回 HTTP 400 + `{code: 10001}`
2. `ResourceNotFoundException` 返回 HTTP 404 + `{code: 10005}`
3. `InternalServerErrorException` 返回 HTTP 500 + `{code: 10007}`
4. 前端能同时读取 `response.status` 和 `response.data.code`

## 注意事项

- HTTP 状态码保持语义化，不将所有错误返回 200
- 业务码 `code` 提供细粒度判断（如区分 404 是文档不存在还是测试用例不存在）
- `error_code` 用于前端 i18n 映射和特殊逻辑处理
