"""通用搜索控制器

POST /api/v1/search — 同步搜索（无白名单过滤，信任内部调用）
"""
import json

from fastapi import APIRouter, Request

from src.core.pipeline.node_context import AuthContext
from src.schemas.common import APIResponse
from src.schemas.search.request import GenericSearchRequest
from src.service.search.search_service import SearchService
from src.utils.logger import logger

router = APIRouter(prefix="/api/v1/search", tags=["搜索"])


@router.post("/")
async def generic_search(request: Request, data: GenericSearchRequest):
    """通用端点同步搜索"""
    search_service: SearchService = request.app.state.search_service
    pipeline_repo = request.app.state.pipeline_repo
    version_repo = request.app.state.version_repo
    tenant_id = request.state.tenant_id
    user_id = request.state.user_id
    roles = getattr(request.state, "roles", [])

    # 获取管道配置
    pipeline = await pipeline_repo.get_by_id(data.pipeline_id, tenant_id)
    if not pipeline:
        return APIResponse.error(code=404, message="管道不存在", error_code="PIPELINE_NOT_FOUND")

    # 获取版本配置
    version_num = data.pipeline_version or pipeline.active_version
    version = await version_repo.get_by_version(data.pipeline_id, version_num, tenant_id)
    if not version:
        return APIResponse.error(
            code=404, message=f"版本 v{version_num} 不存在", error_code="PIPELINE_NOT_FOUND"
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

    # 参数转换
    params = data.params.model_dump()

    # 执行搜索（通用端点无白名单过滤）
    result = await search_service.sync_search(
        pipeline_config=pipeline_config,
        query=data.query,
        params=params,
        auth=auth,
        allowed_param_whitelist=None,
    )

    return APIResponse.success(data=result.model_dump())
