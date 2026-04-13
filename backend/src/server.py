from fastapi import FastAPI
from src.config import settings
from src.controller import (
    task_controller,
    rag_controller,
    rag_test_controller,
    config_controller,
    monitoring_controller,
    prompt_controller,
)
from fastapi.middleware.cors import CORSMiddleware
from src.utils.logger import logger
from pathlib import Path
from contextlib import asynccontextmanager
from src.core.llm.log_collector import LLMLogCollector
from prometheus_client import make_asgi_app


@asynccontextmanager
async def lifespan(app: FastAPI):
    LLMLogCollector.start()
    logger.info("Application startup complete")
    yield
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

    app.add_middleware(
        CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
    )
    app.include_router(task_controller.router)
    app.include_router(rag_controller.router)
    app.include_router(rag_test_controller.router)
    app.include_router(config_controller.router)
    app.include_router(monitoring_controller.router)
    app.include_router(prompt_controller.router)

    metrics_app = make_asgi_app()
    app.mount("/metrics", metrics_app)

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
