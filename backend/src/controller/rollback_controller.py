"""配置回滚控制器

提供配置版本对比和回滚 API。
"""

from typing import Optional

from fastapi import APIRouter, Body, Query

from src.core.database import db_session_factory
from src.schemas import RollbackRequest
from src.schemas.common import APIResponse
from src.service import config_rollback_service
from src.utils.exceptions import ResourceNotFoundException
from src.utils.response import api_handler

router = APIRouter(prefix="/api/v1/rag/test", tags=["RAG Eval Rollback"])


@router.get("/config-versions/compare")
@api_handler("对比配置版本", exception_map={ValueError: ResourceNotFoundException})
async def compare_config_versions(
    from_version: str = Query(..., description="源版本ID"),
    to_version: str = Query(..., description="目标版本ID"),
):
    """对比两个配置版本的差异

    返回两个版本配置快照的差异，包括新增、删除和修改的配置项。
    """
    async with db_session_factory() as session:
        diff = await config_rollback_service.compare_config_versions(
            session=session,
            from_version_id=from_version,
            to_version_id=to_version,
        )
        return APIResponse.success(data=diff)


@router.post("/config-versions/{version_id}/rollback")
@api_handler("配置回滚", exception_map={ValueError: ResourceNotFoundException})
async def rollback_to_version(
    version_id: str,
    request: RollbackRequest,
):
    """回滚到指定配置版本

    创建新的配置版本（复制目标版本快照），并标记为回滚状态。
    """
    async with db_session_factory() as session:
        result = await config_rollback_service.rollback_to_version(
            session=session,
            config_version_id=version_id,
            user_id=request.user_id,
            reason=request.reason,
        )
        # 提交事务
        await session.commit()

        return APIResponse.success(
            data=result,
            message=f"已回滚到版本，新变更集: {result['change_set_label']}",
        )
