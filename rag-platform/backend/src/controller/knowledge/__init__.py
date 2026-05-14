"""知识库模块控制器统一导出"""
from .document_controller import router as document_router
from .kb_controller import router as kb_router
from .rebuild_controller import router as rebuild_router

__all__ = ["kb_router", "document_router", "rebuild_router"]
