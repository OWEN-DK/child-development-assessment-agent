"""
配置健康诊断 API 控制器
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Any

from src.service.config_health_service import ConfigHealthService, hash_config
from src.utils.logger import logger

router = APIRouter(prefix="/api/v1/config", tags=["Config Health"])


class HealthDiagnosticRequest(BaseModel):
    """健康诊断请求"""

    config: dict[str, Any] = Field(..., description="当前配置")


class DiagnosticSuggestion(BaseModel):
    """诊断建议"""

    priority: str  # high/medium/low
    issue: str
    suggestion: str
    config_path: str
    current_value: str
    recommended_value: str


class HealthDiagnosticResponse(BaseModel):
    """健康诊断响应"""

    score: int = Field(..., ge=0, le=100)
    score_basis: str
    suggestions: list[DiagnosticSuggestion]


@router.post("/health", response_model=HealthDiagnosticResponse)
async def run_health_diagnostic(request: HealthDiagnosticRequest):
    """
    LLM 健康度诊断

    - 调用 LLM 分析配置
    - 返回评分与建议
    - 缓存 5 分钟（使用 Redis）
    """
    try:
        from src.service.cache_service import cache_service
        import json

        service = ConfigHealthService()

        # 计算配置哈希（用于缓存）
        config_hash = hash_config(request.config)
        cache_key = f"health_diagnostic:{config_hash}"

        # 检查 Redis 缓存
        cached = await cache_service.get(cache_key)
        if cached:
            logger.debug(f"健康诊断缓存命中: {config_hash[:8]}")
            if isinstance(cached, str):
                return json.loads(cached)
            return cached

        # 调用健康诊断服务
        result = await service.diagnose(request.config)

        # 缓存结果到 Redis（5 分钟）
        await cache_service.set(cache_key, json.dumps(result), expire=300)

        logger.info(f"健康诊断完成: score={result.get('score', 0)}")

        return HealthDiagnosticResponse(**result)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"健康诊断失败: {e}")
        # 降级到本地规则评分
        try:
            service = ConfigHealthService()
            result = service.local_score(request.config)
            return HealthDiagnosticResponse(**result)
        except Exception as fallback_error:
            logger.error(f"降级评分也失败: {fallback_error}")
            raise HTTPException(status_code=500, detail=f"健康诊断失败: {str(e)}")
