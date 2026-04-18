# Phase 3-3: 错误响应格式

> **需求来源**: spec 文档 `unified-api-response-and-error-handling.md` 中 `4.3` 节
> **所属 Phase**: Phase 3

## 需求定义

定义所有错误接口的统一响应格式，采用 `code`（数字）+ `error_code`（字符串）双字段方案。

## 验收标准

- [ ] 错误响应包含 `code`, `message`, `error_code` 三个必填字段
- [ ] `details` 和 `trace_id` 为可选字段
- [ ] HTTP 状态码与业务码映射正确
- [ ] 错误信息统一使用中文

## 涉及文件

| 文件路径 | 操作 | 说明 |
|---------|------|------|
| `backend/src/schemas/common.py` | 已在 01 中定义 | APIResponse.error() |
| `backend/src/utils/exceptions.py` | 修改 | 异常类使用 error() 格式 |

## 实现方案

### 标准错误响应

**HTTP 4xx / 5xx**
```json
{
  "code": 10001,
  "message": "请求参数校验失败",
  "error_code": "INVALID_PARAMS",
  "details": {
    "errors": ["child_profile: field required"]
  },
  "trace_id": "abc-123-def"
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `code` | `int` | 是 | 业务错误码（数字），便于机器判断 |
| `message` | `string` | 是 | 用户可读的错误信息（中文），直接展示给用户 |
| `error_code` | `string` | 是 | 错误码标识（英文大写蛇形），供前端逻辑判断和国际化映射 |
| `details` | `object` | 否 | 错误的额外上下文信息 |
| `trace_id` | `string` | 否 | 请求追踪 ID，便于排查问题 |

### 通过 APIResponse.error() 构造

```python
# 在异常处理器中使用
from src.schemas import APIResponse

async def app_exception_handler(request: Request, exc: AppException):
    return JSONResponse(
        status_code=exc.status_code,
        content=APIResponse.error(
            code=exc.code,
            message=exc.message,
            error_code=exc.error_code,
            details=exc.details,
        ),
    )
```

### 错误码与 HTTP 状态码映射

| HTTP 状态码 | 使用场景 | 业务码范围 | 示例 |
|------------|---------|-----------|------|
| `200` | 请求成功 | `code: 0` | 正常返回 |
| `400` | 参数校验失败、业务规则不通过 | `10001-10099` | 参数格式错误 |
| `401` | 未认证或 Token 过期 | `10003` | 登录过期 |
| `403` | 权限不足 | `10004` | 无操作权限 |
| `404` | 资源不存在 | `10005` + 模块码 | 文档不存在 |
| `409` | 资源冲突/重复 | `10006` | 重复创建 |
| `429` | 请求频率超限 | `10009` | 请求过多 |
| `500` | 服务端内部异常 | `10007` | 系统异常 |
| `503` | 依赖服务不可用 | `10008` | 数据库连接失败 |

## 测试方案

1. 参数校验失败返回 `{code: 10001, error_code: "INVALID_PARAMS"}`
2. 资源不存在返回 `{code: 10005, error_code: "RESOURCE_NOT_FOUND"}`
3. 系统异常返回 `{code: 10007, error_code: "INTERNAL_ERROR"}`
4. 所有错误 message 字段为中文

## 注意事项

- `error_code` 必须为大写蛇形（如 `INVALID_PARAMS`）
- `message` 必须为中文，便于直接展示
- `details` 用于携带额外上下文，如校验失败的字段列表
