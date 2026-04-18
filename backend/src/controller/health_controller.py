from fastapi import APIRouter, Request

from src.schemas import HealthResponse

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/", response_model=HealthResponse)
async def health_check(request: Request):
    """健康检查端点

    返回系统各组件的配置状态。
    前端据此判断是否展示"LLM 未配置"的提示。

    参数:
        request: FastAPI 请求对象

    返回:
        HealthResponse: 包含 LLM 配置状态和缺失的环境变量列表
    """
    missing_vars = getattr(request.app.state, "env_vars_missing", [])
    llm_configured = "DASHSCOPE_API_KEY" not in missing_vars

    return HealthResponse(
        status="healthy" if llm_configured else "degraded",
        llm_configured=llm_configured,
        missing_vars=missing_vars,
    )
