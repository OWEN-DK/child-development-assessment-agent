"""健康检查控制器

路由前缀：/health
"""
from fastapi import APIRouter

from src.api.json_response import APIResponse

router = APIRouter(tags=["健康检查"])


@router.get("/health")
async def health_check():
    """健康检查端点"""
    return APIResponse.success(data={"status": "healthy"})
