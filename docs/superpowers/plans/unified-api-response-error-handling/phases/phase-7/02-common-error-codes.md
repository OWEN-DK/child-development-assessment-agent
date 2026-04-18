# Phase 7-2: 通用错误码

> **需求来源**: spec 文档 `unified-api-response-and-error-handling.md` 中 `8.2` 节
> **所属 Phase**: Phase 7

## 需求定义

定义 10 个通用错误码（10000-10999 范围），覆盖参数校验、权限、系统异常等场景。

## 验收标准

- [ ] 10 个通用错误码定义完整
- [ ] 每个错误码有对应的异常类
- [ ] error_code 为大写蛇形

## 涉及文件

| 文件路径 | 操作 | 说明 |
|---------|------|------|
| `backend/src/utils/error_codes.py` | 修改 | 添加通用错误码常量 |
| `backend/src/utils/exceptions.py` | 修改 | 添加通用异常类 |

## 实现方案

### 错误码常量

```python
# 通用错误码 (10000-10999)
COMMON_SUCCESS = 0
COMMON_INVALID_PARAMS = 10001
COMMON_MISSING_REQUIRED_FIELD = 10002
COMMON_UNAUTHORIZED = 10003
COMMON_FORBIDDEN = 10004
COMMON_RESOURCE_NOT_FOUND = 10005
COMMON_DUPLICATE_RESOURCE = 10006
COMMON_INTERNAL_ERROR = 10007
COMMON_SERVICE_UNAVAILABLE = 10008
COMMON_REQUEST_TIMEOUT = 10009
COMMON_TASK_CANCELLED = 10010
```

### 错误码与 error_code 映射

| 错误码 | error_code | message | 说明 |
|--------|-----------|---------|------|
| `0` | `SUCCESS` | 成功 | 操作成功 |
| `10001` | `INVALID_PARAMS` | 请求参数校验失败 | 参数格式或类型错误 |
| `10002` | `MISSING_REQUIRED_FIELD` | 缺少必填字段 | 必填参数未传 |
| `10003` | `UNAUTHORIZED` | 未授权，请先登录 | 未认证或 Token 过期 |
| `10004` | `FORBIDDEN` | 无权限执行此操作 | 权限不足 |
| `10005` | `RESOURCE_NOT_FOUND` | 请求的资源不存在 | 通用资源不存在 |
| `10006` | `DUPLICATE_RESOURCE` | 资源已存在 | 重复创建 |
| `10007` | `INTERNAL_ERROR` | 系统内部异常，请稍后重试 | 未预期的服务器错误 |
| `10008` | `SERVICE_UNAVAILABLE` | 服务暂时不可用 | 依赖服务异常 |
| `10009` | `REQUEST_TIMEOUT` | 请求超时 | 处理时间过长 |
| `10010` | `TASK_CANCELLED` | 任务已取消 | 异步任务被取消 |

### 异常类（已在 Phase 3-5 中定义）

```python
# 以下异常类已在 exceptions.py 中定义：
# - InvalidParamsException (10001)
# - ResourceNotFoundException (10005)
# - UnauthorizedException (10003)
# - ForbiddenException (10004)
# - DuplicateResourceException (10006)
# - InternalServerErrorException (10007)
# - ServiceUnavailableException (10008)

# 需补充：
class MissingRequiredFieldException(AppException):
    """缺少必填字段"""
    def __init__(self, field: str, message: str | None = None):
        msg = message or f"缺少必填字段: {field}"
        super().__init__(
            status_code=400,
            code=10002,
            message=msg,
            error_code="MISSING_REQUIRED_FIELD",
            details={"field": field},
        )


class RequestTimeoutException(AppException):
    """请求超时"""
    def __init__(self, message: str = "请求超时"):
        super().__init__(
            status_code=429,
            code=10009,
            message=message,
            error_code="REQUEST_TIMEOUT",
        )


class TaskCancelledException(AppException):
    """任务已取消"""
    def __init__(self, message: str = "任务已取消"):
        super().__init__(
            status_code=200,
            code=10010,
            message=message,
            error_code="TASK_CANCELLED",
        )
```

## 测试方案

1. 每个异常类实例化后 code、error_code、message 正确
2. HTTP 状态码与错误码映射正确
3. 前端能通过 error_code 做逻辑判断

## 注意事项

- 通用错误码是全局共享的，新增需审慎
- `MISSING_REQUIRED_FIELD` 与 `INVALID_PARAMS` 区分：前者是必填字段缺失，后者是格式/类型错误
