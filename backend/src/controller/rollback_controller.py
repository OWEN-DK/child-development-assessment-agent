"""配置回滚控制器

提供配置版本对比和回滚 API。
"""

from fastapi import APIRouter, HTTPException, Query, Body
from pydantic import BaseModel
from typing import Optional

from src.core.database import db_session_factory
from src.service import config_rollback_service
from src.utils.logger import logger

router = APIRouter(prefix="/api/v1/rag/test", tags=["RAG Eval Rollback"])


class RollbackRequest(BaseModel):
    """回滚请求体"""

    user_id: str = "anonymous"
    reason: str


@router.get("/config-versions/compare")
async def compare_config_versions(
    from_version: str = Query(..., description="源版本ID"),
    to_version: str = Query(..., description="目标版本ID"),
):
    """对比两个配置版本的差异

    返回两个版本配置快照的差异，包括新增、删除和修改的配置项。
    """
    try:
        async with db_session_factory() as session:
            diff = await config_rollback_service.compare_config_versions(
                session=session,
                from_version_id=from_version,
                to_version_id=to_version,
            )
            return {
                "status": "success",
                "data": diff,
            }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"对比配置版本失败: {e}")
        raise HTTPException(status_code=500, detail=f"对比配置版本失败: {str(e)}")


@router.post("/config-versions/{version_id}/rollback")
async def rollback_to_version(
    version_id: str,
    request: RollbackRequest,
):
    """回滚到指定配置版本

    创建新的配置版本（复制目标版本快照），并标记为回滚状态。
    """
    try:
        async with db_session_factory() as session:
            result = await config_rollback_service.rollback_to_version(
                session=session,
                config_version_id=version_id,
                user_id=request.user_id,
                reason=request.reason,
            )
            # 提交事务
            await session.commit()

            return {
                "status": "success",
                "data": result,
                "message": f"已回滚到版本，新变更集: {result['change_set_label']}",
            }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"配置回滚失败: {e}")
        raise HTTPException(status_code=500, detail=f"配置回滚失败: {str(e)}")
