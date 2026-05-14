"""响应与错误处理工具模块

统一错误处理模式，消除重复的 try/except + logger + HTTPException 模板。
"""

from functools import wraps
from typing import Any, Callable, Dict, Optional, Type

from src.utils.exceptions import (AppException, InternalServerErrorException,
                                  InvalidParamsException,
                                  ResourceNotFoundException)
from src.utils.logger import logger


def handle_api_error(e: Exception, action: str, include_detail: bool = True) -> None:
    """统一错误处理

    使用方式：
        try:
            result = do_something()
        except Exception as e:
            handle_api_error(e, "获取数据")

    Args:
        e: 捕获的异常
        action: 操作描述（如"获取数据"、"创建测试用例"）
        include_detail: 是否在错误信息中包含异常详情
    """
    logger.error(f"{action}失败: {e}", exc_info=True)
    if include_detail:
        raise InternalServerErrorException(f"{action}失败: {str(e)}")
    raise InternalServerErrorException(f"{action}失败")


def not_found(resource: str, detail: Optional[dict] = None) -> None:
    """资源不存在快捷函数

    使用方式：
        if not item:
            not_found("测试用例", {"id": case_id})

    Args:
        resource: 资源名称（如"测试用例"、"文档"）
        detail: 额外上下文信息
    """
    raise ResourceNotFoundException(
        error_code=f"{resource.upper()}_NOT_FOUND",
        message=f"{resource}不存在",
        details=detail,
    )


def server_error(message: str = "系统内部异常，请稍后重试", details: Optional[dict] = None) -> None:
    """系统错误快捷函数

    Args:
        message: 错误信息
        details: 额外上下文信息
    """
    raise InternalServerErrorException(message=message)


def require(condition: bool, exception: AppException) -> None:
    """条件校验快捷函数

    使用方式：
        require(user is not None, UnauthorizedException())
        require(item.owner == current_user, ForbiddenException())

    Args:
        condition: 校验条件
        exception: 条件不满足时抛出的异常
    """
    if not condition:
        raise exception


def api_handler(
    action: str,
    exception_map: Optional[Dict[Type[Exception], Type[AppException]]] = None,
    include_detail: bool = True,
):
    """API错误处理装饰器

    消除重复的 try/except + logger + raise 模板。

    使用方式：
        @router.post("/cases")
        @api_handler("创建测试用例")
        async def create_test_case(request: CreateTestCaseRequest):
            return await service.create(request)

        # 带自定义异常映射
        @router.post("/import")
        @api_handler("导入数据", exception_map={
            ValueError: InvalidParamsException,
            JSONDecodeError: InvalidParamsException,
        })
        async def import_data(file: UploadFile):
            return await service.import_file(file)

    Args:
        action: 操作描述（用于日志和错误消息）
        exception_map: 自定义异常映射 {捕获的异常类型: 抛出的异常类型}
        include_detail: 是否在错误信息中包含异常详情
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                # 检查是否有自定义异常映射
                if exception_map:
                    for exc_type, app_exc_type in exception_map.items():
                        if isinstance(e, exc_type):
                            raise app_exc_type(message=str(e))
                # 默认处理
                handle_api_error(e, action, include_detail)

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                if exception_map:
                    for exc_type, app_exc_type in exception_map.items():
                        if isinstance(e, exc_type):
                            raise app_exc_type(message=str(e))
                handle_api_error(e, action, include_detail)

        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    return decorator


import asyncio

