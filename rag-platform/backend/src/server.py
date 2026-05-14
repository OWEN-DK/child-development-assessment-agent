"""RAG Platform 服务入口

从 backend/ 继承并去业务化：
- 移除：rag_controller、task_controller、rag_eval 相关路由
- 保留：健康检查、监控、配置管理、提示词管理基础设施
- 新增：管道引擎、权限、知识库路由占位
"""
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from prometheus_client import make_asgi_app

from src.config import settings, validate_required_env_vars
from src.controller import config_controller, monitoring_controller
from src.core.config.cache import ConfigCache
from src.core.llm.log_collector import LLMLogCollector
from src.core.redis_client import RedisClient
from src.core.tracing.writer import get_trace_writer
from src.middleware.exception_handler import (
    app_exception_handler,
    global_exception_handler,
    validation_exception_handler,
)
from src.api.json_response import UtcJsonResponse
from src.middleware.response_wrapper import ResponseWrapperMiddleware
from src.utils.exceptions import AppException, ResourceNotFoundException
from fastapi.exceptions import RequestValidationError
from src.utils.logger import logger


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    logger.info("=" * 60)
    logger.info("RAG Platform startup begins")
    logger.info("=" * 60)

    # 启动 LLM 日志收集器
    LLMLogCollector.start()
    logger.info("[1/4] LLMLogCollector started")

    # 启动 TraceWriter 异步队列
    trace_writer = get_trace_writer()
    await trace_writer.start()
    logger.info("[2/4] TraceWriter started")

    # 初始化配置热重载缓存
    try:
        redis_client = RedisClient.get_client()
        config_cache = ConfigCache.get_instance()
        await config_cache.initialize(redis_client)
        logger.info("[3/4] ConfigCache initialized with hot-reload")
    except Exception as e:
        logger.warning(f"ConfigCache 初始化失败，热重载未启用: {e}")

    # 占位：Phase 1 初始化（认证、租户管理）
    # from src.core.auth.initializer import init_auth
    # await init_auth()
    logger.info("[4/4] Auth system placeholder (Phase 1)")

    logger.info("=" * 60)
    logger.info("RAG Platform startup complete")
    logger.info("=" * 60)
    yield

    logger.info("=" * 60)
    logger.info("RAG Platform shutdown begins")
    logger.info("=" * 60)

    # 关闭配置热重载缓存
    try:
        config_cache = ConfigCache.get_instance()
        if config_cache._ever_initialized:
            await config_cache.shutdown()
            logger.info("[1/3] ConfigCache shut down")
        else:
            logger.info("[1/3] ConfigCache was never initialized, skipping")
    except Exception as e:
        logger.warning(f"ConfigCache 关闭异常: {e}")

    # 关闭 TraceWriter 异步队列
    if getattr(trace_writer, '_ever_started', False):
        await trace_writer.stop()
        logger.info("[2/3] TraceWriter shut down")
    else:
        logger.info("[2/3] TraceWriter was never started, skipping")

    # 关闭 LLM 日志收集器
    if LLMLogCollector._ever_started:
        await LLMLogCollector.stop()
        logger.info("[3/3] LLMLogCollector shut down")
    else:
        logger.info("[3/3] LLMLogCollector was never started, skipping")

    logger.info("=" * 60)
    logger.info("RAG Platform shutdown complete")
    logger.info("=" * 60)


def create_app() -> FastAPI:
    """创建 FastAPI 应用实例"""
    logger.info("Initializing RAG Platform...")

    # 确保必要目录存在
    required_dirs = [
        Path(settings.data_dir),
        Path(settings.rag_storage_dir),
        Path(settings.rag_temp_upload_dir),
        Path(settings.rag_storage_dir) / "chroma",
        Path(settings.rag_storage_dir) / "bm25",
        Path(settings.rag_storage_dir) / "documents",
    ]

    for dir_path in required_dirs:
        dir_path.mkdir(parents=True, exist_ok=True)

    app = FastAPI(
        title="RAG Platform",
        version="0.1.0",
        debug=settings.debug,
        lifespan=lifespan,
        default_response_class=UtcJsonResponse,
    )

    # 校验环境变量
    missing_vars = validate_required_env_vars()
    if missing_vars:
        logger.critical(f"关键环境变量缺失: {', '.join(missing_vars)}")
        app.state.env_vars_missing = missing_vars
    else:
        app.state.env_vars_missing = []

    # ── 中间件注册（按执行顺序） ──────────────────────────

    # 1. TRACE_ID 中间件（优先级最高）
    from src.middleware.trace_middleware import TraceMiddleware
    app.add_middleware(TraceMiddleware)

    # 2. 响应包装中间件
    app.add_middleware(ResponseWrapperMiddleware)

    # 3. 占位：认证中间件（Phase 1）
    # from src.middleware.auth_middleware import AuthMiddleware
    # app.add_middleware(AuthMiddleware)

    # 4. 占位：限流中间件（Phase 4）
    # from src.middleware.rate_limit_middleware import RateLimitMiddleware
    # app.add_middleware(RateLimitMiddleware)

    # 5. CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── 异常处理器 ──────────────────────────────────────

    app.add_exception_handler(AppException, app_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, global_exception_handler)

    # ── 路由注册 ────────────────────────────────────────

    # 基础设施路由（继承）
    app.include_router(config_controller.router)
    app.include_router(monitoring_controller.router)

    # 健康检查
    from src.controller.health_controller import router as health_router
    app.include_router(health_router)

    # 占位：管道引擎路由（Phase 3）
    # from src.controller.pipeline.pipeline_controller import router as pipeline_router
    # app.include_router(pipeline_router)

    # 占位：知识库路由（Phase 2）
    # from src.controller.knowledge_base_controller import router as kb_router
    # app.include_router(kb_router)

    # 占位：搜索 API 路由（Phase 4）
    # from src.controller.search_controller import router as search_router
    # app.include_router(search_router)

    # 占位：权限路由（Phase 1）
    # from src.controller.auth_controller import router as auth_router
    # app.include_router(auth_router)

    # ── Prometheus 指标 ─────────────────────────────────

    metrics_app = make_asgi_app()
    app.mount("/metrics", metrics_app)

    # ── SPA 回退路由 ────────────────────────────────────

    frontend_dist_dir = os.path.join(os.path.dirname(__file__), "../../frontend/dist")
    spa_enabled = os.path.isfile(os.path.join(frontend_dist_dir, "index.html"))

    @app.get("/{full_path:path}")
    async def spa_fallback(full_path: str):
        """SPA 回退：非 API 路径返回 index.html"""
        if not spa_enabled:
            raise ResourceNotFoundException(message="页面不存在")

        if full_path.startswith(
            ("api/", "docs", "openapi.json", "metrics", "health", "search/")
        ):
            raise ResourceNotFoundException(message="页面不存在")

        file_path = os.path.join(frontend_dist_dir, full_path)
        if os.path.isfile(file_path):
            return FileResponse(file_path)

        index_path = os.path.join(frontend_dist_dir, "index.html")
        if os.path.isfile(index_path):
            return FileResponse(index_path)

        raise ResourceNotFoundException(message="页面不存在")

    logger.info("RAG Platform initialized successfully")
    return app
