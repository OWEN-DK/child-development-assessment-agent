import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from prometheus_client import make_asgi_app

from src.config import settings, validate_required_env_vars
from src.controller import (config_controller, export_controller,
                            monitoring_controller, rag_controller,
                            rag_test_controller, rollback_controller,
                            task_controller, trend_controller,
                            tuning_controller)
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
    logger.info("=" * 60)
    logger.info("Application startup begins")
    logger.info("=" * 60)

    # 启动 LLM 日志收集器
    LLMLogCollector.start()
    logger.info("[1/5] LLMLogCollector started")

    # 启动 TraceWriter 异步队列
    trace_writer = get_trace_writer()
    await trace_writer.start()
    logger.info("[2/5] TraceWriter started")

    # 初始化默认提示词（幂等操作，已存在则跳过）
    from src.core.prompt_impl.initializer import init_default_prompts

    await init_default_prompts()
    logger.info("[3/5] Default prompts initialized")

    # 启动定时任务调度器
    start_scheduler()
    logger.info("[4/5] APScheduler started")

    # 初始化配置热重载缓存
    try:
        redis_client = RedisClient.get_client()
        config_cache = ConfigCache.get_instance()
        await config_cache.initialize(redis_client)
        logger.info("[5/5] ConfigCache initialized with hot-reload")
    except Exception as e:
        logger.warning(f"ConfigCache 初始化失败，热重载未启用: {e}")

    logger.info("=" * 60)
    logger.info("Application startup complete")
    logger.info("=" * 60)
    yield

    logger.info("=" * 60)
    logger.info("Application shutdown begins")
    logger.info("=" * 60)

    # 关闭配置热重载缓存
    try:
        config_cache = ConfigCache.get_instance()
        if config_cache._ever_initialized:
            await config_cache.shutdown()
            logger.info("[1/4] ConfigCache shut down")
        else:
            logger.info("[1/4] ConfigCache was never initialized, skipping")
    except Exception as e:
        logger.warning(f"ConfigCache 关闭异常: {e}")

    # 关闭 TraceWriter 异步队列（等待队列排空）
    if getattr(trace_writer, '_ever_started', False):
        await trace_writer.stop()
        logger.info("[2/4] TraceWriter shut down")
    else:
        logger.info("[2/4] TraceWriter was never started, skipping")

    # 关闭定时任务调度器
    stop_scheduler()
    logger.info("[3/4] APScheduler shut down")

    # 关闭 LLM 日志收集器
    if LLMLogCollector._ever_started:
        await LLMLogCollector.stop()
        logger.info("[4/6] LLMLogCollector shut down")
    else:
        logger.info("[4/6] LLMLogCollector was never started, skipping")

    # 关闭索引管理器（释放持久化线程）
    try:
        from src.service.index_manager_service import index_manager_service
        if hasattr(index_manager_service, 'shutdown'):
            index_manager_service.shutdown()
            logger.info("[5/6] IndexManagerService shut down")
    except Exception as e:
        logger.warning(f"IndexManagerService 关闭异常: {e}")

    # 关闭磁盘缓存（释放持久化线程）
    try:
        from src.service.cache.facade import cache_facade
        if hasattr(cache_facade, 'shutdown'):
            cache_facade.shutdown()
            logger.info("[6/6] DiskCache shut down")
    except Exception as e:
        logger.warning(f"DiskCache 关闭异常: {e}")

    logger.info("=" * 60)
    logger.info("Application shutdown complete")
    logger.info("=" * 60)


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

    # 注册TRACE_ID中间件（优先级最高，第一个执行）
    from src.middleware.trace_middleware import TraceMiddleware
    app.add_middleware(TraceMiddleware)
    
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

    # Phase 7: 提示词管理（三层编辑模式）
    from src.controller.prompt_management_controller import PromptController

    PromptController().register_routes(app)

    # Phase 6: 趋势、导出、回滚
    app.include_router(trend_controller.router)
    app.include_router(export_controller.router)
    app.include_router(rollback_controller.router)

    # Phase 10: 调优建议 API
    from src.controller import tuning_suggestion_controller

    app.include_router(tuning_suggestion_controller.router)

    # Phase 10: 报告查询 API
    from src.controller import report_controller

    app.include_router(report_controller.router)

    # Phase 8: 审计日志 API
    from src.controller import audit_log_controller

    app.include_router(audit_log_controller.router)

    # Phase 8: 意图标注 API
    from src.controller import intent_annotation_controller

    app.include_router(intent_annotation_controller.router)

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

    # reload 模式下只能使用单 worker
    workers = 1 if settings.app_reload else settings.app_workers

    uvicorn.run(
        "src.server:create_app",
        host=settings.app_host,
        port=int(settings.app_port),
        reload=settings.app_reload,
        workers=workers,
        factory=True,
    )


if __name__ == "__main__":
    main()
