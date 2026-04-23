from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from src.core.tracing.context import trace_context
from src.utils.logger import set_trace_id, get_trace_id


class TraceMiddleware(BaseHTTPMiddleware):
    """TRACE_ID 中间件：为每个请求生成唯一TRACE_ID，并激活完整追踪上下文"""
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
    
    async def dispatch(self, request: Request, call_next) -> Response:
        # 优先从请求头获取TRACE_ID（前端/上游服务传递）
        header_trace_id = request.headers.get("X-Trace-ID")
        
        # 使用 trace_context 包裹请求，激活 TraceWriter 路径
        # 注意：trace_context 会生成新的 trace_id 并写入 contextvars
        # 我们使用请求路径作为 Trace 名称以便识别
        trace_name = f"{request.method} {request.url.path}"
        metadata = {"client_host": request.client.host if request.client else None}
        
        async with trace_context(name=trace_name, metadata=metadata) as tid:
            # 将生成的 trace_id 同步到日志系统
            set_trace_id(tid)
            
            try:
                response = await call_next(request)
                # 将TRACE_ID返回给前端
                response.headers["X-Trace-ID"] = tid
                return response
            finally:
                # 请求结束后清空日志TRACE_ID
                set_trace_id("")
