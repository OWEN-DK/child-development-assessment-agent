"""响应包装中间件

自动将成功响应包装为统一格式:
{
    "code": 0,
    "message": "success",
    "data": {...}
}

跳过以下响应:
- SSE 流式响应 (text/event-stream)
- 文件下载 (Content-Disposition)
- 204/304 状态码
- 已经是错误响应 (HTTP >= 400)
- 已经是统一格式 (包含 code 字段)
"""

import json

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, StreamingResponse

from src.api.json_response import UtcJsonResponse


class ResponseWrapperMiddleware(BaseHTTPMiddleware):
    """自动包装成功响应为统一格式"""

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)

        # 跳过 SSE 流式响应
        if isinstance(response, StreamingResponse):
            content_type = response.headers.get("content-type", "")
            if "text/event-stream" in content_type:
                return response

        # 跳过 204/304
        if response.status_code in (204, 304):
            return response

        # 跳过错误响应
        if response.status_code >= 400:
            return response

        # 检查 Content-Type
        content_type = response.headers.get("content-type", "")
        if "application/json" not in content_type and "json" not in content_type:
            return response

        # 读取响应体
        body = b""
        async for chunk in response.body_iterator:
            body += chunk

        try:
            original_data = json.loads(body)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return Response(
                content=body,
                status_code=response.status_code,
                headers=dict(response.headers),
            )

        # 跳过已包装的响应
        if isinstance(original_data, dict) and "code" in original_data:
            return UtcJsonResponse(
                status_code=response.status_code,
                content=original_data,
            )

        # 包装响应
        wrapped = {
            "code": 0,
            "message": "success",
            "data": original_data,
        }
        return UtcJsonResponse(
            status_code=response.status_code,
            content=wrapped,
        )
