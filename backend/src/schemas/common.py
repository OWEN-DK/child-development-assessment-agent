"""通用模型模块

包含全局共享的 Pydantic 模型：
- APIResponse: 统一响应包装
- PaginatedResponse: 分页响应
- HealthResponse: 健康检查响应
"""

from typing import Any, Generic, Optional, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class HealthResponse(BaseModel):
    """健康检查响应"""

    status: str
    llm_configured: bool
    missing_vars: list[str] = []


class PaginatedResponse(BaseModel, Generic[T]):
    """分页响应数据，嵌套在 APIResponse.data 中

    格式：
    {
        "code": 0,
        "message": "success",
        "data": {
            "items": [...],
            "total": 100,
            "page": 1,
            "page_size": 20
        }
    }
    """

    items: list[T] = Field(default_factory=list, description="当前页数据列表")
    total: int = Field(description="总记录数")
    page: int = Field(ge=1, description="当前页码，从 1 开始")
    page_size: int = Field(ge=1, le=100, description="每页大小")

    @property
    def total_pages(self) -> int:
        """计算总页数"""
        if self.page_size <= 0:
            return 0
        return (self.total + self.page_size - 1) // self.page_size

    @property
    def has_next(self) -> bool:
        """是否有下一页"""
        return self.page < self.total_pages

    @property
    def has_prev(self) -> bool:
        """是否有上一页"""
        return self.page > 1


class APIResponse(BaseModel, Generic[T]):
    """统一 API 响应模型

    成功响应格式：
    {
        "code": 0,
        "message": "success",
        "data": {...}
    }
    """

    code: int = Field(default=0, description="业务状态码，0 表示成功")
    message: str = Field(default="success", description="提示信息")
    data: Optional[T] = Field(default=None, description="业务数据")

    @classmethod
    def success(cls, data: Optional[T] = None, message: str = "success") -> "APIResponse[T]":
        """构造成功响应"""
        return cls(code=0, message=message, data=data)

    @classmethod
    def error(
        cls,
        code: int,
        message: str,
        error_code: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
        trace_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """构造错误字典（用于异常处理器返回）

        错误响应格式：
        {
            "code": 10001,
            "message": "请求参数校验失败",
            "error_code": "INVALID_PARAMS",
            "details": {...},
            "trace_id": "xxx"
        }
        """
        result: dict[str, Any] = {
            "code": code,
            "message": message,
            "error_code": error_code or "UNKNOWN_ERROR",
        }
        if details is not None:
            result["details"] = details
        if trace_id is not None:
            result["trace_id"] = trace_id
        return result
