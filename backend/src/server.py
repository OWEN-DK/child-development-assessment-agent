import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from prometheus_client import make_asgi_app

from src.config import settings, validate_required_env_vars
from src.controller import (config_controller, export_controller,
                            monitoring_controller, prompt_controller,
                            rag_controller, rag_test_controller,
                            rollback_controller, task_controller,
                            trend_controller, tuning_controller)
from src.core.config.cache import ConfigCache
from src.core.llm.log_collector import LLMLogCollector
from src.core.redis_client import RedisClient
from src.core.scheduler import start_scheduler, stop_scheduler
from src.core.tracing.writer import get_trace_writer
from src.utils.exceptions import ResourceNotFoundException
from src.middleware.exception_handler import (app_exception_handler,
                                               global_exception_handler,
                                               validation_exception_handler)
from src.middleware.response_wrapper import ResponseWrapperMiddleware
from src.utils.exceptions import AppException
from fastapi.exceptions import RequestValidationError
from src.utils.logger import logger


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动 LLM 日志收集器
    LLMLogCollector.start()

    # 启动 TraceWriter 异步队列
    trace_writer = get_trace_writer()
    await trace_writer.start()
    logger.info("TraceWriter started")

    # 启动定时任务调度器
    start_scheduler()

    # 初始化配置热重载缓存
    try:
        redis_client = RedisClient.get_client()
        config_cache = ConfigCache.get_instance()
        await config_cache.initialize(redis_client)
        logger.info("ConfigCache 热重载已启用")
    except Exception as e:
        logger.warning(f"ConfigCache 初始化失败，热重载未启用: {e}")

    logger.info("Application startup complete")
    yield

    # 关闭配置热重载缓存
    try:
        config_cache = ConfigCache.get_instance()
        await config_cache.shutdown()
        logger.info("ConfigCache 热重载已关闭")
    except Exception as e:
        logger.warning(f"ConfigCache 关闭异常: {e}")

    # 关闭 TraceWriter 异步队列（等待队列排空）
    await trace_writer.stop()
    logger.info("TraceWriter stopped")

    # 关闭定时任务调度器
    stop_scheduler()

    # 关闭 LLM 日志收集器
    await LLMLogCollector.stop()

    logger.info("Application shutdown complete")


def create_app() -> FastAPI:
    logger.info("Initializing application...")

    required_dirs = [
        Path(settings.data_dir),
        Path(settings.rag_storage_dir),
        Path(settings.rag_temp_upload_dir),
        Path(settings.data_dir) / "configs",
        Path(settings.data_dir) / "configs" / "versions",
        Path(settings.rag_storage_dir) / "vector_store",
        Path(settings.rag_storage_dir) / "index",
        Path(settings.rag_storage_dir) / "snapshots",
        Path(settings.rag_storage_dir) / "source_documents",
        Path(settings.rag_storage_dir) / "test_case_drafts",
        Path(settings.rag_storage_dir) / "test_sets",
        Path(settings.rag_storage_dir) / "test_cases_history",
        Path(settings.rag_storage_dir) / "test_runs",
        Path(settings.data_dir).parent / "cache",
    ]

    created_count = 0
    for dir_path in required_dirs:
        if not dir_path.exists():
            dir_path.mkdir(parents=True, exist_ok=True)
            logger.info(f"Created required directory: {dir_path}")
            created_count += 1

    if created_count > 0:
        logger.info(f"Successfully created {created_count} directories")
    else:
        logger.info("All required directories already exist")

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        debug=settings.debug,
        lifespan=lifespan,
    )

    # 校验环境变量
    missing_vars = validate_required_env_vars()
    if missing_vars:
        logger.critical(f"关键环境变量缺失: {', '.join(missing_vars)}")
        app.state.env_vars_missing = missing_vars
    else:
        app.state.env_vars_missing = []

    # 注册响应包装中间件
    app.add_middleware(ResponseWrapperMiddleware)

    # 注册异常处理器(按优先级从高到低)
    app.add_exception_handler(AppException, app_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, global_exception_handler)

    app.add_middleware(
        CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
    )
    app.include_router(task_controller.router)
    app.include_router(rag_controller.router)
    app.include_router(rag_test_controller.router)
    app.include_router(rag_test_controller.api_router)  # Phase 2: SSE 工作流
    app.include_router(config_controller.router)

    # 配置健康诊断
    from src.controller import config_health_controller

    app.include_router(config_health_controller.router)

    # 健康检查端点
    from src.controller.health_controller import router as health_router

    app.include_router(health_router)

    app.include_router(monitoring_controller.router)
    app.include_router(prompt_controller.router)

    # Phase 6: 趋势、导出、回滚
    app.include_router(trend_controller.router)
    app.include_router(export_controller.router)
    app.include_router(rollback_controller.router)

    from src.core.tuning import (ConflictDetector, HistoryAnalyzer,
                                 LLMDiagnoser, RuleEngine,
                                 TuningSuggestionEngine)

    tuning_engine = TuningSuggestionEngine(
        rule_engine=RuleEngine(),
        history_analyzer=HistoryAnalyzer(),
        llm_diagnoser=LLMDiagnoser(),
        conflict_detector=ConflictDetector(),
    )
    controller = tuning_controller.TuningController(tuning_engine)
    controller.register_routes(app)

    metrics_app = make_asgi_app()
    app.mount("/metrics", metrics_app)

    # SPA 回退路由：非 API 路径的 404 请求返回 index.html
    frontend_dist_dir = os.path.join(os.path.dirname(__file__), "../../frontend/dist")
    spa_enabled = os.path.isfile(os.path.join(frontend_dist_dir, "index.html"))

    @app.get("/{full_path:path}")
    async def spa_fallback(full_path: str):
        """SPA回退路由：将所有非API路径的请求返回index.html，由前端React Router处理"""
        if not spa_enabled:
            raise ResourceNotFoundException(message="页面不存在")

        if full_path.startswith(
            ("api/", "docs", "openapi.json", "metrics", "rag/", "health")
        ):
            raise ResourceNotFoundException(message="页面不存在")

        file_path = os.path.join(frontend_dist_dir, full_path)
        if os.path.isfile(file_path):
            return FileResponse(file_path)

        index_path = os.path.join(frontend_dist_dir, "index.html")
        if os.path.isfile(index_path):
            return FileResponse(index_path)

        raise ResourceNotFoundException(message="页面不存在")

    return app


def main():
    import uvicorn

    uvicorn.run(
        "src.server:create_app",
        host=settings.app_host,
        port=int(settings.app_port),
        reload=settings.app_reload,
        factory=True,
    )


if __name__ == "__main__":
    main()
