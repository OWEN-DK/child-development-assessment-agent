"""发布管理控制器

PUT  /api/v1/pipelines/{id}/publish    — 配置/更新发布 URL
POST /api/v1/pipelines/{id}/unpublish  — 停用发布 URL
GET  /api/v1/pipelines/{id}/publish    — 查询发布状态
GET  /api/v1/published-endpoints       — 列出已发布端点
"""
from fastapi import APIRouter, Query, Request

from src.schemas.common import APIResponse
from src.schemas.search.publish import PublishConfig
from src.service.search.publish_service import PublishService
from src.utils.logger import logger

router = APIRouter(tags=["发布管理"])


@router.put("/api/v1/pipelines/{pipeline_id}/publish")
async def publish_pipeline(
    request: Request, pipeline_id: str, data: PublishConfig
):
    """配置/更新发布 URL"""
    service: PublishService = request.app.state.publish_service
    tenant_id = request.state.tenant_id

    try:
        result = await service.publish(pipeline_id, tenant_id, data)
        return APIResponse.success(data=result.model_dump())
    except ValueError as e:
        error_code = "URL_PATH_CONFLICT" if "URL_PATH_CONFLICT" in str(e) else "INVALID_PARAMS"
        return APIResponse.error(code=400, message=str(e), error_code=error_code)


@router.post("/api/v1/pipelines/{pipeline_id}/unpublish")
async def unpublish_pipeline(request: Request, pipeline_id: str):
    """停用发布 URL"""
    service: PublishService = request.app.state.publish_service
    tenant_id = request.state.tenant_id

    try:
        result = await service.unpublish(pipeline_id, tenant_id)
        return APIResponse.success(data=result.model_dump())
    except ValueError as e:
        return APIResponse.error(code=404, message=str(e), error_code="PIPELINE_NOT_FOUND")


@router.get("/api/v1/pipelines/{pipeline_id}/publish")
async def get_publish_status(request: Request, pipeline_id: str):
    """查询发布状态"""
    service: PublishService = request.app.state.publish_service
    tenant_id = request.state.tenant_id

    result = await service.get_status(pipeline_id, tenant_id)
    return APIResponse.success(data=result.model_dump())


@router.get("/api/v1/published-endpoints")
async def list_published_endpoints(
    request: Request,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    enabled: bool = Query(default=None),
    keyword: str = Query(default=None),
):
    """列出当前租户已发布端点"""
    service: PublishService = request.app.state.publish_service
    tenant_id = request.state.tenant_id

    result = await service.list_endpoints(
        tenant_id, page, page_size, enabled, keyword
    )
    return APIResponse.success(data=result.model_dump())
