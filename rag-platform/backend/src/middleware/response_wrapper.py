"""响应包装中间件

自动将成功响应包装为统一格式:
{
    "code": 0,
    "message": "success",
    "data": {...}
}
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

        if isinstance(response, StreamingResponse):
            content_type = response.headers.get("content-type", "")
            if "text/event-stream" in content_type:
                return response

        if response.status_code in (204, 304):
            return response

        if response.status_code >= 400:
            return response

        content_type = response.headers.get("content-type", "")
        if "application/json" not in content_type and "json" not in content_type:
            return response

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

        if isinstance(original_data, dict) and "code" in original_data:
            return UtcJsonResponse(
                status_code=response.status_code,
                content=original_data,
            )

        wrapped = {
            "code": 0,
            "message": "success",
            "data": original_data,
        }
        return UtcJsonResponse(
            status_code=response.status_code,
            content=wrapped,
        )
