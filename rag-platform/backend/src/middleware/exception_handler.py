"""全局异常处理器

按优先级从高到低:
1. AppException - 自定义业务异常
2. RequestValidationError - 请求参数校验异常
3. ValueError / KeyError - 业务校验/数据缺失异常 (→ 400)
4. Exception - 兜底处理 (→ 500)
"""

import uuid

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

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


async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
    """处理 ValueError: 通常是业务校验或数据缺失,返回 400"""
    logger.warning(
        "ValueError in request: %s | path=%s",
        exc,
        request.url.path,
    )
    return JSONResponse(
        status_code=400,
        content=APIResponse.error(
            code=10001,
            message=str(exc),
            error_code="INVALID_PARAMS",
        ),
    )


async def key_error_handler(request: Request, exc: KeyError) -> JSONResponse:
    """处理 KeyError: 键/类型缺失,返回 400"""
    logger.warning(
        "KeyError in request: %s | path=%s",
        exc,
        request.url.path,
    )
    return JSONResponse(
        status_code=400,
        content=APIResponse.error(
            code=10001,
            message=str(exc),
            error_code="INVALID_PARAMS",
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
            message="系统内部异常,请稍后重试",
            error_code="INTERNAL_ERROR",
            details={"trace_id": trace_id},
        ),
    )
