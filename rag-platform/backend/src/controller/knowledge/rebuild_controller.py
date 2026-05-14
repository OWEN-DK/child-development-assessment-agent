"""重建任务控制器

路由前缀：/api/v1/knowledge-bases/{kb_id}/rebuild
"""
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from src.api.json_response import APIResponse
from src.service.knowledge.rebuild_service import RebuildService
from src.utils.logger import logger

router = APIRouter(
    prefix="/api/v1/knowledge-bases/{kb_id}/rebuild",
    tags=["重建任务"],
)


@router.post("/")
async def trigger_rebuild(request: Request, kb_id: str):
    """触发重建"""
    service: RebuildService = request.app.state.rebuild_service
    tenant_id = request.state.tenant_id

    task_id = await service.trigger_rebuild(kb_id, tenant_id, "manual")
    return APIResponse.success(data={"task_id": task_id})


@router.get("/status")
async def get_rebuild_status(request: Request, kb_id: str):
    """获取重建状态"""
    service: RebuildService = request.app.state.rebuild_service
    tenant_id = request.state.tenant_id

    result = await service.get_status(kb_id, tenant_id)
    return APIResponse.success(data=result.model_dump())


@router.get("/stream")
async def stream_rebuild_progress(request: Request, kb_id: str):
    """SSE 推送重建进度"""
    service: RebuildService = request.app.state.rebuild_service

    return StreamingResponse(
        service.sse_publisher.event_stream(kb_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
