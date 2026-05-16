"""SSE 流式搜索控制器

POST /api/v1/search/stream — SSE 流式搜索
"""
import asyncio
import json
import uuid

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from src.api.sse import SSEPublisher
from src.core.pipeline.node_context import AuthContext
from src.schemas.search.request import StreamSearchRequest
from src.service.search.search_service import SearchService
from src.utils.logger import logger

router = APIRouter(tags=["搜索流式"])

# SSE 配置
_SSE_TIMEOUT_SECONDS = 300  # 5 分钟


def _format_sse(data: dict) -> str:
    """将字典格式化为 SSE data 行"""
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


def _error_stream(message: str, error_code: str = "PIPELINE_NOT_FOUND"):
    """构建错误 SSE 流"""
    async def stream():
        yield _format_sse({
            "type": "run_failed",
            "error_message": message,
            "error_code": error_code,
        })
        yield _format_sse({"type": "close", "code": 1000, "reason": "error"})
    return stream()


@router.post("/api/v1/search/stream")
async def stream_search(request: Request, data: StreamSearchRequest):
    """SSE 流式搜索"""
    search_service: SearchService = request.app.state.search_service
    pipeline_repo = request.app.state.pipeline_repo
    version_repo = request.app.state.version_repo
    tenant_id = request.state.tenant_id
    user_id = request.state.user_id
    roles = getattr(request.state, "roles", [])

    # 获取管道配置
    pipeline = await pipeline_repo.get_by_id(data.pipeline_id, tenant_id)
    if not pipeline:
        return StreamingResponse(
            _error_stream("管道不存在"),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    version_num = data.pipeline_version or pipeline.active_version
    version = await version_repo.get_by_version(data.pipeline_id, version_num, tenant_id)
    if not version:
        return StreamingResponse(
            _error_stream(f"版本 v{version_num} 不存在"),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    pipeline_config = json.loads(version.config_snapshot)

    # 构建认证上下文
    auth = AuthContext(
        tenant_id=tenant_id,
        user_id=user_id,
        roles=roles,
        role_slugs=getattr(request.state, "role_slugs", []),
        is_superadmin=getattr(request.state, "is_superadmin", False),
    )

    # 生成 run_id 和 SSE 频道
    run_id = str(uuid.uuid4()).replace("-", "")[:16]
    channel = f"search:{run_id}"

    # 参数转换
    params = data.params.model_dump()

    # 先订阅 SSE 频道（必须在启动后台任务前完成，避免丢失事件）
    sse_generator = SSEPublisher.subscribe(channel)

    # 启动后台搜索任务
    asyncio.create_task(
        search_service.stream_search(
            pipeline_config=pipeline_config,
            query=data.query,
            params=params,
            auth=auth,
            publish_channel=channel,
        )
    )

    # 返回 SSE 流
    return StreamingResponse(
        sse_generator,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "X-Run-Id": run_id,
        },
    )
