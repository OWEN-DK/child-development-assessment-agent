# Phase 3-1: APIResponse 模型定义

> **需求来源**: spec 文档 `unified-api-response-and-error-handling.md` 中 `4.1-4.3` 节
> **所属 Phase**: Phase 3

## 需求定义

定义统一的 API 响应模型 `APIResponse`，作为所有接口成功响应的标准包装。

## 验收标准

- [ ] `APIResponse` 定义在 `schemas/common.py`
- [ ] 包含 `code`、`message`、`data` 三个字段
- [ ] 提供 `success()` 类方法
- [ ] 提供 `error()` 类方法（返回 dict，用于异常处理器）

## 涉及文件

| 文件路径 | 操作 | 说明 |
|---------|------|------|
| `backend/src/schemas/common.py` | 修改 | 添加 APIResponse 定义 |

## 实现方案

```python
"""
通用模型 - API 响应、分页、基础异常等
"""

from typing import Any, Optional

from pydantic import BaseModel, Field


class APIResponse(BaseModel, generic_alias=True):
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
    data: Optional[Any] = Field(default=None, description="业务数据")

    @classmethod
    def success(cls, data: Any = None, message: str = "success") -> "APIResponse":
        """构造成功响应"""
        return cls(code=0, message=message, data=data)

    @classmethod
    def error(
        cls,
        code: int,
        message: str,
        error_code: Optional[str] = None,
        details: Optional[dict] = None,
        trace_id: Optional[str] = None,
    ) -> dict:
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
```

## 使用示例

```python
# Controller 中使用
from src.schemas import APIResponse

@router.get("/tasks/{task_id}")
async def get_task(task_id: str):
    task = await find_task(task_id)
    return APIResponse.success(data={"task": task})

@router.post("/tasks")
async def create_task(req: CreateTaskRequest):
    task = await save_task(req)
    return APIResponse.success(data={"id": task.id}, message="创建成功")
```

## 测试方案

```python
def test_api_response_success():
    resp = APIResponse.success(data={"key": "value"})
    assert resp.code == 0
    assert resp.message == "success"
    assert resp.data == {"key": "value"}

def test_api_response_success_with_message():
    resp = APIResponse.success(data=None, message="操作成功")
    assert resp.message == "操作成功"

def test_api_response_error():
    err = APIResponse.error(code=10001, message="参数错误", error_code="INVALID_PARAMS")
    assert err["code"] == 10001
    assert err["error_code"] == "INVALID_PARAMS"
    assert "details" not in err

def test_api_response_error_with_details():
    err = APIResponse.error(
        code=10001,
        message="参数错误",
        error_code="INVALID_PARAMS",
        details={"field": "name"},
        trace_id="abc-123",
    )
    assert err["details"] == {"field": "name"}
    assert err["trace_id"] == "abc-123"
```

## 注意事项

- `error()` 返回 dict 而非 `APIResponse` 实例，因为异常处理器需要返回 JSONResponse
- `data` 字段类型为 `Optional[Any]`，可为 null、对象、数组
