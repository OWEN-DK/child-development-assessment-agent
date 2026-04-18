"""检索服务 - 向后兼容入口

本文件已重构为子服务架构，此处仅保留向后兼容的导出。
所有业务逻辑已迁移至 src.service.retrieval 子模块。
"""

from src.service.retrieval.facade import RetrievalFacade, get_retrieval_facade

# 向后兼容：保持 RetrievalService 名称可用
RetrievalService = RetrievalFacade

# 向后兼容：保持 retrieval_service 单例可用
_retrieval_service_instance = None


def get_retrieval_service(index_manager, cache_service):
    """获取检索服务单例（向后兼容）"""
    global _retrieval_service_instance
    if _retrieval_service_instance is None:
        _retrieval_service_instance = get_retrieval_facade(index_manager, cache_service)
    return _retrieval_service_instance


# 导出单例变量名（延迟初始化，避免循环依赖）
def _init_retrieval_service():
    """延迟初始化 retrieval_service"""
    global _retrieval_service_instance, retrieval_service
    from src.service.cache_service import cache_service
    from src.service.index_manager_service import IndexManagerService
    index_mgr = IndexManagerService()
    _retrieval_service_instance = get_retrieval_facade(index_mgr, cache_service)
    retrieval_service = _retrieval_service_instance

# 触发初始化
_init_retrieval_service()
