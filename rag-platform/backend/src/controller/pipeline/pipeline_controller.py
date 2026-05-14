"""管道控制器

路由前缀：/api/v1/pipelines
"""
from typing import Optional

from fastapi import APIRouter, Query, Request

from src.api.json_response import APIResponse
from src.schemas.pipeline.pipeline import PipelineCreate, PipelineUpdate
from src.service.pipeline.pipeline_service import PipelineService
from src.utils.logger import logger

router = APIRouter(prefix="/api/v1/pipelines", tags=["管道管理"])


@router.post("/")
async def create_pipeline(request: Request, data: PipelineCreate):
    """创建管道"""
    service: PipelineService = request.app.state.pipeline_service
    tenant_id = request.state.tenant_id
    user_id = request.state.user_id

    result = await service.create(data, tenant_id, user_id)
    return APIResponse.success(data=result.model_dump())


@router.get("/")
async def list_pipelines(
    request: Request,
    status: Optional[str] = Query(default=None),
    keyword: Optional[str] = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
):
    """列出管道"""
    service: PipelineService = request.app.state.pipeline_service
    tenant_id = request.state.tenant_id

    result = await service.list(tenant_id, status=status, keyword=keyword, skip=skip, limit=limit)
    return APIResponse.success(data=result.model_dump())


@router.get("/{pipeline_id}")
async def get_pipeline(request: Request, pipeline_id: str):
    """获取管道详情"""
    service: PipelineService = request.app.state.pipeline_service
    tenant_id = request.state.tenant_id

    result = await service.get(pipeline_id, tenant_id)
    return APIResponse.success(data=result.model_dump())


@router.put("/{pipeline_id}")
async def update_pipeline(request: Request, pipeline_id: str, data: PipelineUpdate):
    """更新管道配置"""
    service: PipelineService = request.app.state.pipeline_service
    tenant_id = request.state.tenant_id

    result = await service.update(pipeline_id, data, tenant_id)
    return APIResponse.success(data=result.model_dump())


@router.delete("/{pipeline_id}")
async def delete_pipeline(request: Request, pipeline_id: str):
    """删除管道"""
    service: PipelineService = request.app.state.pipeline_service
    tenant_id = request.state.tenant_id

    await service.delete(pipeline_id, tenant_id)
    return APIResponse.success(data=None)


@router.get("/{pipeline_id}/versions")
async def get_versions(request: Request, pipeline_id: str):
    """获取版本列表"""
    service: PipelineService = request.app.state.pipeline_service
    tenant_id = request.state.tenant_id

    result = await service.get_versions(pipeline_id, tenant_id)
    return APIResponse.success(data=[v.model_dump() for v in result])


@router.get("/{pipeline_id}/versions/{version_number}")
async def get_version(request: Request, pipeline_id: str, version_number: int):
    """获取指定版本"""
    service: PipelineService = request.app.state.pipeline_service
    tenant_id = request.state.tenant_id

    result = await service.get_version(pipeline_id, version_number, tenant_id)
    return APIResponse.success(data=result.model_dump())


@router.post("/{pipeline_id}/rollback/{version_number}")
async def rollback(request: Request, pipeline_id: str, version_number: int):
    """回滚到指定版本"""
    service: PipelineService = request.app.state.pipeline_service
    tenant_id = request.state.tenant_id

    result = await service.rollback(pipeline_id, version_number, tenant_id)
    return APIResponse.success(data=result.model_dump())


@router.post("/compare")
async def compare_versions(
    request: Request,
    pipeline_id: str = Query(...),
    v1: int = Query(...),
    v2: int = Query(...),
):
    """对比两个版本"""
    service: PipelineService = request.app.state.pipeline_service
    tenant_id = request.state.tenant_id

    result = await service.compare(pipeline_id, v1, v2, tenant_id)
    return APIResponse.success(data=result.model_dump())
