# Phase 7-6: 响应包装中间件

> **需求来源**: spec 文档 `unified-api-response-and-error-handling.md` 中 `9.2` 节
> **所属 Phase**: Phase 7

## 需求定义

实现 `ResponseWrapperMiddleware`，自动将成功响应包装为统一格式，跳过 SSE、文件下载等特殊响应。

## 验收标准

- [ ] 成功响应自动包装为 `{code: 0, message: "success", data: {...}}`
- [ ] SSE 响应不参与包装
- [ ] 文件下载响应不参与包装
- [ ] 已经是统一格式的响应不重复包装
- [ ] 错误响应（HTTP 4xx/5xx）不参与包装

## 涉及文件

| 文件路径 | 操作 | 说明 |
|---------|------|------|
| `backend/src/middleware/response_wrapper.py` | 新增 | 响应包装中间件 |
| `backend/src/server.py` | 修改 | 注册中间件 |

## 实现方案

### 中间件实现

```python
"""
响应包装中间件

自动将成功响应包装为统一格式：
{
    "code": 0,
    "message": "success",
    "data": {...}
}

跳过以下响应：
- SSE 流式响应 (text/event-stream)
- 文件下载 (Content-Disposition)
- 204/304 状态码
- 已经是错误响应 (HTTP >= 400)
- 已经是统一格式 (包含 code 字段)
"""

import json

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response, StreamingResponse


class ResponseWrapperMiddleware(BaseHTTPMiddleware):
    """自动包装成功响应为统一格式"""

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)

        # 跳过 SSE 流式响应
        if isinstance(response, StreamingResponse):
            content_type = response.headers.get("content-type", "")
            if "text/event-stream" in content_type:
                return response

        # 跳过 204/304 状态码
        if response.status_code in (204, 304):
            return response

        # 跳过错误响应
        if response.status_code >= 400:
            return response

        # 跳过非 JSON 响应
        content_type = response.headers.get("content-type", "")
        if "application/json" not in content_type and "json" not in content_type:
            return response

        # 提取响应体
        body = b""
        async for chunk in response.body_iterator:
            body += chunk

        # 尝试解析 JSON
        try:
            original_data = json.loads(body)
        except (json.JSONDecodeError, UnicodeDecodeError):
            # 非 JSON 响应，原样返回
            return JSONResponse(
                status_code=response.status_code,
                content=body.decode("utf-8", errors="replace"),
                headers=dict(response.headers),
            )

        # 如果已经是统一格式（包含 code 字段），不重复包装
        if isinstance(original_data, dict) and "code" in original_data:
            return JSONResponse(
                status_code=response.status_code,
                content=original_data,
                headers=dict(response.headers),
            )

        # 包装为统一格式
        wrapped = {
            "code": 0,
            "message": "success",
            "data": original_data,
        }
        return JSONResponse(
            status_code=response.status_code,
            content=wrapped,
            headers=dict(response.headers),
        )
```

### 注册到 FastAPI

```python
# backend/src/server.py 中修改

from src.middleware.response_wrapper import ResponseWrapperMiddleware


def create_app() -> FastAPI:
    app = FastAPI(title="儿童发展评估 Agent", version="1.0.0")

    # 注册响应包装中间件
    app.add_middleware(ResponseWrapperMiddleware)

    # 注册异常处理器
    # ...

    return app
```

## 改造策略

### 渐进式改造

**Phase 1：中间件自动包装**
- 新增中间件，自动包装所有成功响应
- 旧接口无需修改，自动获得统一格式

**Phase 2：Controller 显式包装**
- 逐个 Controller 改为显式 `return APIResponse.success(data)`
- 显式包装的接口不再被中间件重复包装（因已有 code 字段）

**Phase 3：移除中间件**
- 所有接口显式包装后，移除中间件
- 消除中间件的性能开销

## 测试方案

```python
def test_middleware_wraps_dict_response():
    """测试中间件包装字典响应"""
    # 原响应: {"tasks": [...]}
    # 包装后: {"code": 0, "message": "success", "data": {"tasks": [...]}}

def test_middleware_skips_sse():
    """测试中间件跳过 SSE 响应"""
    # SSE 响应不被包装

def test_middleware_skips_error_response():
    """测试中间件跳过错误响应"""
    # HTTP 400+ 响应不被包装

def test_middleware_skips_already_wrapped():
    """测试中间件不重复包装"""
    # 已有 code 字段的响应不被重复包装

def test_middleware_skips_file_download():
    """测试中间件跳过文件下载"""
    # 文件下载响应不被包装
```

## 注意事项

- 中间件有性能开销（需读取完整响应体），最终目标是移除
- SSE 响应通过 `content-type: text/event-stream` 识别
- 文件下载通过 `Content-Disposition` 头识别
- 过渡期新旧接口可并存
