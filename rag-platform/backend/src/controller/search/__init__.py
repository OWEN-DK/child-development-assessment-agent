"""搜索模块控制器统一导出"""
from .publish_controller import router as publish_router
from .search_controller import router as search_router
from .stream_controller import router as stream_router

__all__ = ["search_router", "stream_router", "publish_router"]
