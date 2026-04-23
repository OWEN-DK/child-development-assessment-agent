"""检索服务 - 向后兼容入口

本文件已重构为子服务架构，此处仅保留向后兼容的导出。
所有业务逻辑已迁移至 src.service.retrieval 子模块。
"""

from src.service.retrieval.facade import RetrievalFacade, get_retrieval_facade

# 向后兼容：保持 RetrievalService 名称可用
RetrievalService = RetrievalFacade

# 向后兼容：保持 retrieval_service 单例可用
_retrieval_service_instance = None
retrieval_service = None


def get_retrieval_service(index_manager = None, cache_service = None):
    """获取检索服务单例（向后兼容）"""
    global _retrieval_service_instance, retrieval_service
    if _retrieval_service_instance is None:
        if not index_manager or not cache_service:
            # 从DI容器获取依赖
            from src.core.di_container import injector
            from src.core.interfaces import IIndexManager, ICacheService
            index_manager = injector.get(IIndexManager)
            cache_service = injector.get(ICacheService)
        _retrieval_service_instance = get_retrieval_facade(index_manager, cache_service)
        retrieval_service = _retrieval_service_instance
    return _retrieval_service_instance
