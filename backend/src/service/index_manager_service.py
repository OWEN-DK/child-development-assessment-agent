"""
向后兼容模块：IndexManagerService 已拆分为子服务模块。
此文件保留原有导入路径的兼容性。
"""
from src.service.index_manager import (IndexManagerService, IndexOperations,
                                       StorageManager)

# 保持单例向后兼容
_index_manager_service_instance = None


def get_index_manager_service():
    """获取索引管理服务单例（向后兼容）"""
    global _index_manager_service_instance
    if _index_manager_service_instance is None:
        _index_manager_service_instance = IndexManagerService()
    return _index_manager_service_instance


# 延迟初始化单例
def _init_service():
    global _index_manager_service_instance, index_manager_service
    _index_manager_service_instance = IndexManagerService()
    index_manager_service = _index_manager_service_instance

_init_service()

__all__ = [
    "IndexManagerService",
    "StorageManager",
    "IndexOperations",
    "index_manager_service",
    "get_index_manager_service",
]
