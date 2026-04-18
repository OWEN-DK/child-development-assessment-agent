"""
向后兼容模块：DocumentIngestionService 已拆分为子服务模块。
此文件保留原有导入路径的兼容性。
"""
from src.service.document_ingestion import (BookIngestor,
                                            DocumentIngestionService,
                                            TaskStateManager, TaskStatus)
from src.service.document_ingestion import \
    task_state_manager as import_task_manager

# 保持单例向后兼容
_document_ingestion_service_instance = None


def get_document_ingestion_service(index_manager):
    """获取文档导入服务单例（向后兼容）"""
    global _document_ingestion_service_instance
    if _document_ingestion_service_instance is None:
        _document_ingestion_service_instance = DocumentIngestionService(index_manager)
    return _document_ingestion_service_instance


# 延迟初始化单例
def _init_service():
    global _document_ingestion_service_instance, document_ingestion_service
    from src.service.index_manager_service import IndexManagerService
    index_mgr = IndexManagerService()
    _document_ingestion_service_instance = DocumentIngestionService(index_mgr)
    document_ingestion_service = _document_ingestion_service_instance

_init_service()

__all__ = [
    "DocumentIngestionService",
    "BookIngestor",
    "TaskStateManager",
    "import_task_manager",
    "TaskStatus",
    "document_ingestion_service",
    "get_document_ingestion_service",
]
