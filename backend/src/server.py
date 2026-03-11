from fastapi import FastAPI
from src.config.settings import settings
from src.controller import task_controller, rag_controller
from fastapi.middleware.cors import CORSMiddleware
from src.utils.logger import logger

def create_app() -> FastAPI:
    logger.info("Initializing application...")
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        debug=settings.debug)

    # 跨域配置
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"]
    )
    app.include_router(task_controller.router)
    app.include_router(rag_controller.router)
    return app

def main():
    import uvicorn
    uvicorn.run(
        "src.server:create_app",
        host=settings.app_host,
        port=int(settings.app_port),
        reload=settings.app_reload,
        factory=True
    )

if __name__ =="__main__":
    main()